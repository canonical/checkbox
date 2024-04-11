#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
#
# Authors:
#    Po-Hsu Lin <po-hsu.lin@canonical.com>
#    Yung Shen <yung.shen@canonical.com>
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

import sys
import time

import checkbox_support.bt_helper as bt_helper

from argparse import ArgumentParser


def unpair_all(devices, manager):
    """Unpairing paired devices and scanning again for rerun jobs."""
    for dev in devices:
        try:
            print("INFO: Unpairing", dev)
            dev.unpair()
        except bt_helper.BtException as exc:
            print("Warning: Unpairing failed", exc)
    else:
        # print(flush=True) to bypass plainbox output buffer,
        # see LP: #1569808 for more details.
        print(
            "Please reset the device to pairing mode in 13 seconds", flush=True
        )
        time.sleep(13)
        print("INFO: Re-scaning for devices in pairing mode", flush=True)
        manager.scan()


def main():
    """Add argument parser here and do most of the job."""
    parser = ArgumentParser(
        description=(
            "Bluetooth auto paring and connect. " "Please select one option."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--mac", type=str, help="Pair with a given MAC, not using scan result,"
    )
    group.add_argument(
        "--mouse",
        action="store_const",
        const="input-mouse",
        dest="target",
        help="List and pair with mouse devices",
    )
    group.add_argument(
        "--keyboard",
        action="store_const",
        const="input-keyboard",
        dest="target",
        help="List and pair with keyboard devices",
    )
    args = parser.parse_args()

    manager = bt_helper.BtManager()
    # Power on bluetooth adapter and scanning devices in advance.
    manager.ensure_adapters_powered()
    manager.scan()

    if args.mac:
        # TODO check MAC format
        print("INFO: Trying to pair with {}".format(args.mac))
        device = list(manager.get_bt_devices(filters={"Address": args.mac}))
        paired_device = list(
            manager.get_bt_devices(
                filters={"Address": args.mac, "Paired": True}
            )
        )
        if not device:
            print("ERROR: No pairable device found, terminating")
            return 1

        unpair_all(paired_device, manager)

        for dev in device:
            try:
                dev.pair()
            except bt_helper.BtException as exc:
                print("ERROR: Unable to pair: ", exc)
                return 1
            else:
                print("INFO: Device paired")
                return 0
    else:
        print("INFO: Listing targeting devices")
        # Listing device based on RSSI
        paired_targets = list(
            manager.get_bt_devices(
                category=bt_helper.BT_ANY,
                filters={"Paired": True, "Icon": args.target},
            )
        )
        if not paired_targets:
            print("INFO: No paired targeting devices found")
            manager.scan()
        else:
            unpair_all(paired_targets, manager)

        target_devices = sorted(
            manager.get_bt_devices(
                category=bt_helper.BT_ANY,
                filters={"Paired": False, "Icon": args.target},
            ),
            key=lambda x: int(x.rssi or -255),
            reverse=True,
        )
        if not target_devices:
            print("ERROR: No target devices found, terminating")
            return 1
        print("INFO: Detected devices (sorted by RSSI; highest first).")
        # let's assing numbers to devices
        devices = dict(enumerate(target_devices, 1))
        for num, dev in devices.items():
            print("{}. {} (RSSI: {})".format(num, dev, dev.rssi))
        chosen = False
        while not chosen:
            print("Which one would you like to connect to? (0 to exit)")
            num = input()
            # TODO: enter as default to 1st device
            if num == "0":
                return 1
            chosen = num.isnumeric() and int(num) in devices.keys()
        print("INFO: {} chosen.".format(devices[int(num)]))
        print("INFO: Pairing selected device..")
        try:
            devices[int(num)].pair()
        except bt_helper.BtException as exc:
            print("ERROR: something wrong: ", exc)
            return 1
        else:
            print("Paired successfully.")
            return 0
    # capture all other silence failures
    return 1


if __name__ == "__main__":
    sys.exit(main())
