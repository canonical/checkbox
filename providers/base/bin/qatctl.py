#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# qatctl.py
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
#
# Authors: Hector Cao <hector.cao@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
Intel QuickAssist Technology (QAT) control utility
"""

import argparse
from enum import Enum
import json
import pathlib
from pprint import *
import re
import subprocess
import sys

"""
---------------------------
Driver Name | PFid | VFid
---------------------------
4xxx        | 4940 | 4941
4xxx        | 4942 | 4943 (OOT Intel driver is 401xx)
4xxx        | 4944 | 4945 (OOT Intel driver is 402xx)
420xx       | 4946 | 4947
---------------------------
"""
QAT_PF_PCI_DEVICE_IDS = [
    {"pf_id": "4940", "vf_id": "4941", "driver": "4xxx"},
    {"pf_id": "4942", "vf_id": "4943", "driver": "4xxx"},
    {"pf_id": "4944", "vf_id": "4945", "driver": "4xxx"},
    {"pf_id": "4946", "vf_id": "4947", "driver": "420xx"},
]


class ExtendedEnum(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


def get_pci_ids(device_id: str, vendor_id: str = ""):
    args: List[str] = ["lspci", "-d", f"{vendor_id}:{device_id}"]
    devices = subprocess.check_output(
        args, universal_newlines=True
    ).splitlines()
    return [v.split(" ")[0] for v in devices]


def get_vfio(bdf: str):
    vfio_path = pathlib.Path("/dev/vfio/")
    vfio_files = vfio_path.glob("*")
    for vfio_file in vfio_files:
        vfio_group = vfio_file.name
        if vfio_group != "vfio" and vfio_group != "devices":
            iommu_path = pathlib.Path(
                f"/sys/kernel/iommu_groups/{vfio_group}/devices/"
            )
            devices = iommu_path.glob("*")
            for dev_path in devices:
                if dev_path.name == bdf:
                    return int(vfio_group)
    return 0


class VFIOGroup(dict):
    def __init__(self, vfio_group, qat_dev):
        self.__setitem__("vfio_dev", f"/dev/vfio/{vfio_group}")
        self.sys_path = pathlib.Path(
            f"/sys/kernel/iommu_groups/{vfio_group}/devices/{qat_dev.bdf}"
        )
        self.__setitem__("numa_node", self.numa())

    def numa(self):
        path = self.sys_path / "numa_node"
        with path.open() as f:
            data = f.read()
        return data.replace("\n", "")

    def __str__(self):
        return json.dumps(self, indent=2)


class CounterType(ExtendedEnum):
    UTILIZATION = "util"
    EXECUTION = "exec"


class CounterEngine(ExtendedEnum):
    CIPHER = "cph"
    AUTHENTICATION = "ath"
    PUBLIC_KEY_ENCRYPT = "pke"
    UNIFIED_CRYPTO_SLICE = "ucs"
    COMPRESSION = "cpr"
    DECOMPRESSION = "dcpr"
    TRANSLATOR = "xlt"


class DeviceData(dict):
    """
    Parse data from
      /sys/kernel/debug/qat_<device>_<BDF>/telemetry/device_data
    and put it as a dictionary.
    """

    def __init__(self):
        self.regex = re.compile(f"(util|exec)_([a-zA-Z]+)(\\d+)")

    def avg(self, counter_type: CounterType, engine: CounterEngine):
        try:
            values = self.__getitem__(f"{counter_type.value}_{engine.value}")
        except:
            return -1
        return sum(values) / len(values)

    def parse(self, data: str):
        self.clear()
        lines = data.splitlines()
        for l in lines:
            fields = l.split()
            counter_name = fields[0]
            value = fields[1]
            # counter_name start with [util|exec] and ends with number
            # -> slice -> must create an array
            m = self.regex.match(l)
            values = value
            if m:
                counter_name = f"{m.group(1)}_{m.group(2)}"
                # index = int(m.group(3))
                values = self.get(counter_name)
                if not values:
                    values = []
                values.append(int(value))

            # filtering
            if not QatDevManager.filter_counter(counter_name):
                continue

            self.__setitem__(counter_name, values)

    def __str__(self):
        return json.dumps(self, indent=2)


class QatDeviceTelemetry(dict):
    def __init__(self, telemetry_path: pathlib.Path):
        self.debugfs_enabled = False
        self.telemetry_path = telemetry_path
        self.debugfs_control_path = self.telemetry_path / "control"
        try:
            f = self.debugfs_control_path.open()
            self.debugfs_enabled = True
        except Exception as e:
            pass

        self.__setitem__("device_data", DeviceData())

    def is_debugfs_enabled(self):
        return self.debugfs_enabled

    def debugfs_fn(func):
        def debugfs_wrapper(self):
            if self.is_debugfs_enabled():
                func(self)

        return debugfs_wrapper

    @debugfs_fn
    def enable_telemetry(self):
        telemetry_path = self.telemetry_path / "control"
        with telemetry_path.open("w+") as f:
            # 1 to enabled, 2,3,4 enabled and collect 2,3,4 values
            f.write("1\n")

    @debugfs_fn
    def collect(self):
        telemetry_path = self.telemetry_path / "device_data"
        lines = []
        with telemetry_path.open() as f:
            data = f.read()
            self.get("device_data").parse(data)

    @debugfs_fn
    def control(self):
        with self.debugfs_control_path.open() as f:
            return f.read()

    def __str__(self):
        return json.dumps(self, indent=2)


class QatDeviceDebugfs(dict):
    def __init__(self, debugfs_path: pathlib.Path):
        self.path = debugfs_path
        self.parser = {}
        files = self.path.glob("*")
        for f in files:
            fname = f
            self.__setitem__(f"f.name", {})

        self.__setitem__(
            "telemetry", QatDeviceTelemetry(self.path / "telemetry")
        )
        self.get("telemetry").enable_telemetry()

        self.__setitem__("dev_cfg", self.read("dev_cfg"))

    def read(self, name):
        dev_cfg_path = self.path / name
        with dev_cfg_path.open() as f:
            return f.read()

    def __str__(self):
        return json.dumps(self, indent=2)


class Qat4xxxDevice:
    def __init__(
        self,
        pci_device_id: dict,
        pci_id: str,
        is_virtual_function=False,
        parent_pf=None,
    ):
        self.pci_device_id = pci_device_id
        self.pci_id = pci_id
        self.bdf = f"0000:{self.pci_id}"
        self.is_virtual_function = is_virtual_function
        self.parent_pf = parent_pf
        self.sys_path = pathlib.Path(f"/sys/bus/pci/devices/{self.bdf}/")

        if not self.is_virtual_function:
            driver = self.pci_device_id["driver"]
            self.debugfs = QatDeviceDebugfs(
                pathlib.Path(f"/sys/kernel/debug/qat_{driver}_{self.bdf}")
            )

        if self.is_virtual_function:
            # vfio
            self.vfio = None
            vfio_group = get_vfio(self.bdf)
            if vfio_group >= 0:
                try:
                    self.vfio = VFIOGroup(vfio_group, self)
                except:
                    self.vfio = None
            return

        # this device is a PF
        # build list of VFs
        self._build_vfs()

    def _build_vfs(self):
        self.vfs = []
        vf_pci_device_id = self.pci_device_id["vf_id"]
        pci_ids = get_pci_ids(vf_pci_device_id)
        for pci_id in pci_ids:
            try:
                qat_dev = Qat4xxxDevice(
                    vf_pci_device_id,
                    pci_id,
                    is_virtual_function=True,
                    parent_pf=self,
                )
                if self._check_vf(qat_dev):
                    self.vfs.append(qat_dev)
            except:
                # if the vfio is not setup properly, the creation of the virtual device might fail
                pass

    def _check_vf(self, vf):
        pci_ids = self.pci_id.split(":")
        vf_pci_ids = vf.pci_id.split(":")
        return pci_ids[0] == vf_pci_ids[0]

    def set_state(self, state):
        path = self.sys_path / "qat" / "state"
        with path.open("w+") as f:
            f.write(state)

    def set_auto_reset(self, auto_reset):
        path = self.sys_path / "qat" / "auto_reset"
        with path.open("w+") as f:
            if auto_reset:
                f.write("on")
            else:
                f.write("off")

    def set_cfg_services(self, service):
        self.set_state("down")
        path = self.sys_path / "qat" / "cfg_services"
        with path.open("w+") as f:
            f.write(service)
        self.set_state("up")

    @property
    def numa_node(self):
        path = self.sys_path / "numa_node"
        with path.open() as f:
            data = f.read()
        return data.replace("\n", "")

    @property
    def state(self):
        path = self.sys_path / "qat" / "state"
        with path.open() as f:
            data = f.read()
        return data.replace("\n", "")

    @property
    def auto_reset(self):
        path = self.sys_path / "qat" / "auto_reset"
        with path.open() as f:
            data = f.read()
        return data.replace("\n", "")

    @property
    def cfg_services(self):
        path = self.sys_path / "qat" / "cfg_services"
        with path.open() as f:
            data = f.read()
        return data.replace("\n", "")

    def __repr__(self):
        if self.is_virtual_function:
            return f"{self.pci_id}\t{self.vfio}"
        else:
            # :<10 : to add space padding
            str = f"NUMA_{self.numa_node}\t{self.pci_id}\t{self.sys_path}\t{self.cfg_services :<10}\t{self.state}"
            # virtual function
            if len(self.vfs) > 0:
                str += "\n"
            for vf in self.vfs:
                vfio_dev = "null"
                if vf.vfio:
                    vfio_dev = vf.vfio["vfio_dev"]
                str += f"\t VF: {vf.pci_id} - {vfio_dev}\n"
            return str


class QatDevManager:
    """
    Physical QAT device manager
    """

    counters = None

    def __init__(self, filter_devs=[]):
        self.qat_devs = []

        for device_id in QAT_PF_PCI_DEVICE_IDS:
            pci_ids = get_pci_ids(device_id["pf_id"])
            _devs = []
            for pci_desc in pci_ids:
                pci_id = pci_desc.split(" ")[0]
                if (filter_devs is None) or (pci_id in filter_devs):
                    try:
                        _devs.append(Qat4xxxDevice(device_id, pci_id))
                    except FileNotFoundError as e:
                        # in some cases, the QAT device might not be available in the sysfs and debugfs
                        # for example, it has been passthrough in a VM, we do not want to crash
                        pass
                    except Exception as e:
                        print(
                            f"Exception occured to instanciate QAT device : {e}"
                        )
            self.qat_devs.extend(_devs)

    def filter_counter(counter_name):
        if QatDevManager.counters and (
            counter_name not in QatDevManager.counters
        ):
            return False
        return True

    def collect_telemetry(self):
        for d in self.qat_devs:
            d.debugfs.get("telemetry").collect()

    def print_telemetry(self):
        for d in self.qat_devs:
            print(d.debugfs.get("telemetry"))

    def list_devices(self, short: bool):
        for d in self.qat_devs:
            if short:
                driver = d.pci_device_id["driver"]
                print(f"{d.pci_id} {driver}")
            else:
                print(d)

    def set_state(self, state):
        for d in self.qat_devs:
            d.set_state(state)

    def set_cfg_services(self, service):
        for d in self.qat_devs:
            d.set_cfg_services(service)

    def get_state(self):
        for d in self.qat_devs:
            print(d.state)

    def get_telemetry_data(self):
        for d in self.qat_devs:
            try:
                telemetry = d.debugfs["telemetry"]
                telemetry.collect()
                print(telemetry)
            except:
                sys.exit(1)

    def print_vfio(self):
        for d in self.qat_devs:
            for vf in d.vfs:
                if vf.vfio:
                    print(vf.vfio["vfio_dev"])

    def print_vf(self):
        for d in self.qat_devs:
            for vf in d.vfs:
                print(vf.bdf)

    def print_cfg(self):
        for d in self.qat_devs:
            print(f"BDF: {d.bdf}")
            print("---")
            print("dev_cfg:")
            pprint(d.debugfs.get("dev_cfg"))
            print("VFs:")
            pprint(d.vfs)


def list_dev(args, qat_manager):
    qat_manager.list_devices(args.short)


def status_dev(args, qat_manager):
    if args.vfio:
        qat_manager.print_vfio()
    elif args.vf:
        qat_manager.print_vf()
    else:
        qat_manager.print_cfg()


# Check arguments and call requested function
def qatctl(opts, p):
    qat_manager = QatDevManager(opts.devices)

    if opts.set_state:
        print(f"Set device state : {opts.set_state}")
        qat_manager.set_state(opts.set_state)
        return

    if opts.get_state:
        qat_manager.get_state()
        return

    if opts.get_telemetry_data:
        qat_manager.get_telemetry_data()
        return

    if opts.set_service:
        print(f"Set device service : {opts.set_service}")
        qat_manager.set_cfg_services(opts.set_service)
        print(f"Please restart qat service to update the config")
        return

    opts.func(opts, qat_manager)


# * sym;asym: the device is configured for running crypto
#   services
# * asym;sym: identical to sym;asym
# * dc: the device is configured for running compression services
# * dcc: identical to dc but enables the dc chaining feature,
#   hash then compression. If this is not required chose dc
# * sym: the device is configured for running symmetric crypto
#   services
# * asym: the device is configured for running asymmetric crypto
#   services
# * asym;dc: the device is configured for running asymmetric
#   crypto services and compression services
# * dc;asym: identical to asym;dc
# * sym;dc: the device is configured for running symmetric crypto
#   services and compression services
# * dc;sym: identical to sym;dc
cfg_services = [
    "sym;asym",
    "asym;sym",
    "dc",
    "dcc",
    "sym",
    "asym",
    "asym,dc",
    "dc;asym",
    "sym;dc",
    "dc;sym",
]


def main():
    parser = argparse.ArgumentParser(description=f"QAT control utility")
    parser.add_argument(
        "-d",
        "--devices",
        nargs="+",
        default=None,
        help="select devices for the command (space separated)",
    )
    parser.add_argument(
        "--set-state",
        type=str,
        default=None,
        choices=["up", "down"],
        help="set device state (for all devices if no specific device is specified)",
    )
    parser.add_argument(
        "--set-service",
        type=str,
        default=None,
        choices=cfg_services,
        help="set device service (for all devices if no specific device is specified)",
    )
    parser.add_argument(
        "--get-state",
        action="store_true",
        default=False,
        help="get device state",
    )
    parser.add_argument(
        "--get-telemetry-data",
        action="store_true",
        default=False,
        help="get device telemetry data",
    )
    list_group = parser.add_argument_group("list group")
    subparser = parser.add_subparsers()
    parser_list_dev = subparser.add_parser("list")
    parser_list_dev.add_argument(
        "--short",
        "-s",
        action="store_true",
        default=False,
        help="list devices (PF)",
    )
    parser_list_dev.set_defaults(func=list_dev)
    status_group = parser.add_argument_group("status group")
    parser_status = subparser.add_parser("status")
    parser_status.add_argument(
        "-d",
        "--devices",
        nargs="+",
        default=None,
        help="select devices for the command (space separated)",
    )
    parser_status.add_argument(
        "--vf", action="store_true", default=False, help="list VF devices"
    )
    parser_status.add_argument(
        "--vfio",
        action="store_true",
        default=False,
        help="list VFIO devices for all VFs",
    )
    parser_status.set_defaults(func=status_dev)
    results = parser.parse_args()
    qatctl(results, parser)


if __name__ == "__main__":
    raise SystemExit(main())
