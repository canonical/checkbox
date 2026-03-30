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

import re
import argparse


def dump_firmware_test_mapping(args) -> None:
    firmware_mapping = args.mapping
    firmware_path = args.path
    pattern = r"(\w*):([\w\.-]*):([\w-]*)"
    output_format = "device: {}\nfirmware: {}\ntest_method: {}\npath: {}\n"

    re_result = re.findall(pattern, firmware_mapping)
    if not re_result or firmware_path.strip() == "":
        print("UnexpectedPath: {}".format(firmware_path))
        print("UnexpectedFirmwareMapping: {}".format(firmware_mapping))
        return

    for data in re_result:
        print(output_format.format(data[0], data[1], data[2], firmware_path))


def register_arguments():
    parser = argparse.ArgumentParser(description="RPMSG reload firmware test")

    parser.add_argument(
        "--mapping",
        help="The mapping with RPMSG node and M-Core firmware",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--path",
        help="The directory to store M-core ELF firmware",
        type=str,
        required=True,
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = register_arguments()
    dump_firmware_test_mapping(args)
