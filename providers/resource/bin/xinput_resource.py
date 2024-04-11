#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
#
import os
import sys

from argparse import ArgumentParser

from checkbox_support.parsers.xinput import (
    IXinputResult,
    XinputParser,
)


# Command to retrieve xinput information.
COMMAND = "xinput --list --long"


class XinputResult(IXinputResult):

    def __init__(self):
        self.elements = []

    def addXinputDevice(self, device):
        device["type"] = "device"
        self.elements.append(device)

    def addXinputDeviceClass(self, device, device_class):
        device_class["type"] = "class"
        device_class.update(device)
        self.elements.append(device_class)


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "filename", nargs="?", help="Optional filename containing xinput data"
    )
    args = parser.parse_args()

    if args.filename:
        stream = open(args.filename)
    else:
        stream = os.popen(COMMAND)

    xinput = XinputParser(stream)

    result = XinputResult()
    xinput.run(result)

    for element in result.elements:
        for key, value in element.items():
            if isinstance(value, (list, tuple)):
                print("%s:" % key)
                for v in value:
                    print(" %s" % v)
            else:
                print("%s: %s" % (key, value))

        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
