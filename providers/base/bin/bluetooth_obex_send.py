#!/usr/bin/env python3
#
# Copyright (C) 2026 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import argparse
import logging
import re
import sys

from pathlib import Path
from subprocess import PIPE, run
from bluetooth_test import ObexFTPTest


def scan_available_target():
    print(
        "Scanning for available OBEX targets (up to 30 seconds)...", flush=True
    )
    try:
        discovery = run(
            ["bluetoothctl", "--timeout", "30", "scan", "bredr"],
            stdout=PIPE,
            universal_newlines=True,
        )
        if discovery.returncode:
            raise RuntimeError("Bluetooth discovery failed")
        return discovery.stdout
    except OSError as error:
        raise RuntimeError("Bluetooth discovery failed: {}".format(error))


def obex_test(image, address):

    scan_raw_data = scan_available_target()
    addresses = [addr.strip().upper() for addr in address.split(",")]
    available_targets = [
        addr for addr in addresses if addr in scan_raw_data.upper()
    ]
    if not available_targets:
        print("No available BT devices found in scan.")
        return False

    print(
        "Discovered configured OBEX targets: {}".format(
            ", ".join(available_targets)
        ),
        flush=True,
    )
    for address in available_targets:
        print("Host:[{}]".format(address), flush=True)
        try:
            print("OBEX server BTDEVADDR:[{}]".format(address), flush=True)
            if ObexFTPTest(image, address).send() == 0:
                return True
        except OSError as error:
            print("Bluetooth test failed for [{}]: {}".format(address, error))

    print("No available BT devices succeeded in OBEX transfer.")
    return False


def register_arguments():
    parser = argparse.ArgumentParser(
        description="Send an image over Bluetooth OBEX"
    )
    parser.add_argument(
        "btdevaddr",
        help="comma-separated Bluetooth target addresses",
    )
    parser.add_argument(
        "image",
        help="path to the image to send",
    )
    args = parser.parse_args()
    if not args.btdevaddr.strip():
        parser.error("btdevaddr must not be empty")
    for address in args.btdevaddr.split(","):
        if not re.fullmatch(
            r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", address.strip()
        ):
            parser.error(
                "btdevaddr must contain comma-separated addresses in "
                "AA:BB:CC:DD:EE:FF format"
            )
    if not Path(args.image).is_file():
        parser.error(
            "image must be an existing regular file: {}".format(args.image)
        )
    try:
        with open(args.image, "rb"):
            pass
    except OSError as error:
        parser.error("image cannot be read: {}".format(error))
    return args


def main():
    args = register_arguments()
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(levelname)s: %(message)s",
    )
    try:
        return 0 if obex_test(args.image, args.btdevaddr) else 1
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
