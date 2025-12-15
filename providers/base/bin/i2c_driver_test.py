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
        result = subprocess.check_output(["i2cdetect", "-l"], universal_newlines=True)
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
                        "Test failed, expecting {} I2C " "buses.".format(args.bus)
                    )


class Device:
    """Detect I2C device."""

    def invoked(self, args):
        # Make sure that we have root privileges
        if os.geteuid() != 0:
            raise SystemExit("Error: please run this command as root")
        # Calculate number of buses
        result = subprocess.check_output(["i2cdetect", "-l"], universal_newlines=True)
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
                print("Ignoring bus id: {}, name: {}\n".format(bus_id, bus_name))
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


class I2cDriverTest:
    """I2C driver test."""

    def main(self):
        subcommands = {"bus": Bus, "device": Device}
        parser = argparse.ArgumentParser(
            epilog="NOTE: When using 'device', the IGNORED_I2C_BUSES "
            "environment variable is respected and should contain "
            "a comma-separated list of bus names to ignore."
        )
        parser.add_argument("subcommand", type=str, choices=subcommands)
        parser.add_argument(
            "-b",
            "--bus",
            type=int,
            default=0,
            help="Expected number of I2C bus.",
        )
        args = parser.parse_args()
        subcommands[args.subcommand]().invoked(args)


if __name__ == "__main__":
    I2cDriverTest().main()
