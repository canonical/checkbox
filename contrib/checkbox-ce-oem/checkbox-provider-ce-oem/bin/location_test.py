#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Stanley Huang <stanley.huang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import argparse
import re
import subprocess


def identify_gps_module(serial_device, msg_protocol="NMEA0183"):
    """
    Recognize the GPS module by gpsctl utility

    Args:
        serial_device (str): the serial device node. e.g. /dev/ttyUSB0
        msg_protocol (str):
    """
    cmd = "gpsctl -f -T 60 -D 4 {}".format(serial_device)
    output = subprocess.check_output(
        cmd, shell=True, text=True, universal_newlines=True
    )

    pattern = (
        r"([a-zA-Z0-9\/-]*) identified as a ([a-zA-Z0-9]*) at [0-9]* baud."
    )
    match = re.search(pattern, output)
    if match:
        tty_node, cur_msg_protocol = match.groups()
        if msg_protocol and cur_msg_protocol != msg_protocol:
            raise RuntimeError(
                (
                    "Failed: GPS module been detected, "
                    "but the message protocol is not expected. "
                    "Protocol: {}".format(cur_msg_protocol)
                )
            )
        print(
            "Passed: GPS module (w/ {} protocol) been detected via {}".format(
                cur_msg_protocol, tty_node
            )
        )
        return

    raise RuntimeError(
        (
            "Failed: GPS module not available or "
            "it was detected but not expected protocol"
        )
    )


def dump_gps_resource(mapping):
    """
    Print out the tty node and message protocol of GPS modules

    Args:
        mapping (str):
            a mapping of tty node and message protocol for GPS modules
            e.g.
                "/dev/ttyS0:NMEA0183 /dev/ttyS2"
            Note: you could skip it if any protocol is fine.
    """
    output = ""
    resource_text = "tty_node: {}\nmessage_protocol: {}\n\n"
    for map_data in mapping.split():
        tmp = map_data.split(":")
        tty = tmp[0]
        protocol = tmp[1] if len(tmp) > 1 else ""
        output += resource_text.format(tty, protocol)
    print(output)


def main():
    args = register_arguments()
    if args.test_func == "gps-detection":
        identify_gps_module(args.tty_serial, args.message_protocol)
    elif args.test_func == "dump-gps-resource":
        dump_gps_resource(args.mapping)


def register_arguments():
    parser = argparse.ArgumentParser(
        description="Location (GPS) tests",
    )

    sub_parsers = parser.add_subparsers(dest="test_func")
    sub_parsers.required = True

    detect_test_parser = sub_parsers.add_parser("detection")
    detect_test_parser.add_argument(
        "-t",
        "--tty-serial",
        required=True,
        type=str,
    )
    detect_test_parser.add_argument(
        "--message-protocol",
        type=str,
        default="NMEA0183",
    )
    detect_test_parser.set_defaults(test_func="gps-detection")

    arg_parser = sub_parsers.add_parser("resource")
    arg_parser.add_argument(
        "mapping",
        help=(
            "Usage of parameter: GPS_DEVICES="
            "{tty_node}:{gps_msg_protocol} {tty_node}:{gps_msg_protocol}"
        ),
    )

    arg_parser.set_defaults(test_func="dump-gps-resource")

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    main()
