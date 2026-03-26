#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

from typing import List, Dict

from checkbox_ng.support.release_info import get_release_info
from checkbox_ng.support.parsers.meminfo import MeminfoParser
from checkbox_ng.support.parsers.udevadm import parse_udevadm_output
from checkbox_ng.support.parsers import _json_fallback
from checkbox_ng.support.snap_utils.snapd import Snapd

"""
Device Information Collector

Script that collects information about the device under test and returns it
as JSON.
"""


def get_kernel_cmdline(cmdline_path="/proc/cmdline") -> str:
    with open(cmdline_path) as fp:
        cmdline = fp.read().strip()
    return cmdline


def get_kernel_modules(modules_path="/proc/modules") -> List[Dict]:
    """
    Get information about all the available kernel modules

    Each line in the modules file consists of the following information for
    each module:

    name:         Name of the module.
    size:         Memory size of the module, in bytes.
    instances:    How many instances of the module are currently loaded.
    dependencies: If the module depends upon another module to be present
                  in order to function, and lists those modules.
    state:        The load state of the module: Live, Loading or Unloading.
    offset:       Current kernel memory offset for the loaded module.
    """
    kernel_modules = []
    with open(modules_path) as f:
        for line in f.readlines():
            line = line.strip()
            if line:
                name, size, instances, dependencies, state, offset = (
                    line.split(" ")[:6]
                )
                if dependencies == "-":
                    dependencies = ""

                kernel_modules.append(
                    {
                        "name": name,
                        "size": int(size),
                        "instances": int(instances),
                        "dependencies": [
                            d
                            for d in dependencies.strip().strip(",").split(",")
                        ],
                        "state": state,
                        "offset": int(offset, 16),
                    }
                )
    return kernel_modules


def get_devices():
    cmd = ["udevadm", "info", "--export-db"]
    udevadm_output = subprocess.check_output(cmd, universal_newlines=True)
    devices = parse_udevadm_output(udevadm_output)
    return devices


def get_bios_info() -> dict:
    """
    Retrieve BIOS information from sysfs.

    Usually, Linux provides the following information in /sys/class/dmi/id/:
    - bios_date
    - bios_release
    - bios_vendor
    - bios_version

    This function extracts the content from these files and returns a dict,
    using the filename as a key, defaulting to `None` if it cannot find data.

    In addition, it provides the boot mode by checking the existence of the
    /sys/firmware/efi directory.
    """
    bios_data = {
        "date": None,
        "release": None,
        "vendor": None,
        "version": None,
    }
    bios_root = Path("/sys/class/dmi/id/")
    bios_data_name = "bios_{}"
    for key in sorted(bios_data.keys()):
        try:
            value = (
                (bios_root / bios_data_name.format(key)).read_text().strip()
            )
            bios_data[key] = value
        except (PermissionError, FileNotFoundError) as e:
            print(
                "Failed to read bios {}. Error: {}".format(key, e),
                file=sys.stderr,
            )
    if Path("/sys/firmware/efi").is_dir():
        boot_mode = "UEFI"
    else:
        boot_mode = "BIOS"
    bios_data["boot_mode"] = boot_mode
    return bios_data


def get_debian_packages():
    cmd = ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"]
    output = subprocess.check_output(cmd, universal_newlines=True)
    packages = []
    for line in output.splitlines():
        name, version, arch = line.split("\t")
        pkg = {"name": name, "version": version, "architecture": arch}
        packages.append(pkg)
    return packages


def get_meminfo():
    return MeminfoParser().run()


def get_snap_packages():
    return Snapd().list()


def get_uname():
    return {
        "system": platform.system(),
        "node": platform.node(),
        "kernel": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Collect device information as JSON"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True
    subparsers.add_parser(
        "kernel_cmdline", help="Return kernel command line information"
    )
    subparsers.add_parser(
        "kernel_modules", help="Return modules loaded in the kernel"
    )
    subparsers.add_parser(
        "devices", help="Return devices found by the udeadvm parser"
    )
    subparsers.add_parser(
        "debian_packages", help="Return installed package information"
    )
    subparsers.add_parser(
        "distribution",
        help="Return information about the Linux distribution being used",
    )
    subparsers.add_parser(
        "bios", help="Return BIOS information provided by /sys/class/dmi/id/"
    )
    subparsers.add_parser("memory", help="Return memory information")
    subparsers.add_parser(
        "snaps", help="Return information about installed Snaps"
    )
    subparsers.add_parser("uname", help="Return uname information")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    command_map = {
        "distribution": get_release_info,
        "kernel_cmdline": get_kernel_cmdline,
        "kernel_modules": get_kernel_modules,
        "devices": get_devices,
        "debian_packages": get_debian_packages,
        "bios": get_bios_info,
        "memory": get_meminfo,
        "snaps": get_snap_packages,
        "uname": get_uname,
    }

    if args.command:
        getter = command_map[args.command]
        print(
            json.dumps(
                getter(), indent=4, sort_keys=True, default=_json_fallback
            )
        )


if __name__ == "__main__":
    main()
