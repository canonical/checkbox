#!/usr/bin/env python3
# Copyright 2016-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Gavin Lin <gavin.lin@canonical.com>
#             Sylvain Pineau <sylvain.pineau@canonical.com>
#             Jonathan Cave <jonathan.cave@canonical.com>

"""
This script will check number of detected I2C buses or devices

To see how to use, please run "./i2c_driver_test.py"
"""

import argparse
import os
import subprocess


class Bus:
    """Detect I2C bus."""

    def invoked(self, args):
        """Method called when the command is invoked."""
        # Detect I2C buses and calculate number of them
        result = subprocess.check_output(
            ["i2cdetect", "-l"], universal_newlines=True
        )
        print(result)
        bus_number = len(result.splitlines())
        print("Detected bus number: {}".format(bus_number))

        # Test failed if no I2C bus detected
        if bus_number == 0:
            raise SystemExit("Test failed, no bus detected.")

        # Verify if detected number of buses is as expected
        else:
            if args.bus != 0:
                if bus_number == args.bus:
                    print("Test passed")
                else:
                    raise SystemExit(
                        "Test failed, expecting {} I2C "
                        "buses.".format(args.bus)
                    )


class Device:
    """Detect I2C device."""

    def invoked(self, args):
        # Make sure that we have root privileges
        if os.geteuid() != 0:
            raise SystemExit("Error: please run this command as root")
        # Calculate number of buses
        result = subprocess.check_output(
            ["i2cdetect", "-l"], universal_newlines=True
        )
        detected_i2c_bus = []
        for line in result.splitlines():
            fields = line.split("\t")
            bus_id = fields[0].split("-")[1]
            bus_name = fields[2].strip()
            detected_i2c_bus.append((bus_id, bus_name))
        print("Detected buses: {}".format(detected_i2c_bus))

        ignored_i2c_buses = list(
            filter(
                lambda e: e != "",
                map(
                    str.strip,
                    os.environ.get("IGNORED_I2C_BUSES", "").split(","),
                ),
            )
        )
        print("Ignored buses: {}".format(ignored_i2c_buses))

        # Detect device on each bus
        exit_code = 1
        for bus_id, bus_name in detected_i2c_bus:
            if bus_name in ignored_i2c_buses:
                print(
                    "Ignoring bus id: {}, name: {}\n".format(bus_id, bus_name)
                )
                continue

            print("Checking I2C bus id: {}, name: {}".format(bus_id, bus_name))
            result = subprocess.check_output(
                ["i2cdetect", "-y", "-r", str(bus_id)], universal_newlines=True
            )
            print(result)
            result_lines = result.splitlines()[1:]
            for r in result_lines:
                address_value = r.strip("\n").split(":")[1].split()
                for v in address_value:
                    if v != "--":
                        exit_code = 0
        if exit_code == 1:
            raise SystemExit("No I2C device detected on any I2C bus")
        print("I2C device detected")


class Address:
    """Check that an expected I2C device address responds on a bus."""

    def invoked(self, args):
        # Make sure that we have root privileges
        if os.geteuid() != 0:
            raise SystemExit("Error: please run this command as root")
        if args.address is None:
            raise SystemExit("Error: -a/--address is required")
        address = int(args.address, 16)
        result = subprocess.check_output(
            ["i2cdetect", "-y", "-r", str(args.bus)], universal_newlines=True
        )
        print(result)
        state = None
        for line in result.splitlines()[1:]:
            if ":" not in line:
                continue
            if int(line.split(":", 1)[0], 16) == address & 0xF0:
                # i2cdetect rows are fixed-width: 3 chars per cell, the
                # first cell starting at column 4
                offset = 4 + 3 * (address & 0x0F)
                state = line[offset : offset + 2].strip() or None
        if state is None:
            raise SystemExit(
                "Test failed, address 0x{:02x} was not scanned by i2cdetect "
                "on bus {}".format(address, args.bus)
            )
        if state == "--":
            raise SystemExit(
                "Test failed, no device detected at address 0x{:02x} on "
                "bus {}".format(address, args.bus)
            )
        print(
            "Device detected at address 0x{:02x} on bus {} ({})".format(
                address, args.bus, state
            )
        )


class ExpectedDeviceResource:
    """Print expected I2C devices from configuration as resource records."""

    def invoked(self, args):
        entries = os.environ.get("EXPECTED_I2C_DEVICES", "")
        for entry in filter(None, map(str.strip, entries.split(","))):
            try:
                bus, _, address = entry.partition(":")
                print("bus: {}".format(int(bus)))
                print("address: 0x{:02x}".format(int(address, 16)))
                print()
            except ValueError:
                raise SystemExit(
                    "Invalid EXPECTED_I2C_DEVICES entry: '{}', expected "
                    "<bus>:<address> e.g. 1:0x2d".format(entry)
                )


class I2cDriverTest:
    """I2C driver test."""

    def main(self):
        subcommands = {
            "bus": Bus,
            "device": Device,
            "address": Address,
            "resource": ExpectedDeviceResource,
        }
        parser = argparse.ArgumentParser(
            epilog="NOTE: When using 'device', the IGNORED_I2C_BUSES "
            "environment variable is respected and should contain "
            "a comma-separated list of bus names to ignore. "
            "When using 'resource', the EXPECTED_I2C_DEVICES environment "
            "variable should contain a comma-separated list of "
            "<bus>:<address> entries, e.g. '1:0x2d,1:0x68'."
        )
        parser.add_argument("subcommand", type=str, choices=subcommands)
        parser.add_argument(
            "-b",
            "--bus",
            type=int,
            default=0,
            help="Expected number of I2C buses ('bus') or the bus number "
            "to scan ('address').",
        )
        parser.add_argument(
            "-a",
            "--address",
            type=str,
            help="Expected I2C device address in hex, e.g. 0x2d "
            "('address' only).",
        )
        args = parser.parse_args()
        subcommands[args.subcommand]().invoked(args)


if __name__ == "__main__":
    I2cDriverTest().main()
