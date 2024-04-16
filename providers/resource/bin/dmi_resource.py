#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2011 Canonical Ltd.
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

from checkbox_support.parsers.dmidecode import DmidecodeParser


# Command to retrieve dmi information.
COMMAND = "dmidecode"


class DmiResult:

    attributes = (
        "path",
        "category",
        "product",
        "vendor",
        "serial",
        "version",
        "size",
        "form",
        "sku",
    )

    def addDmiDevice(self, device):
        for attribute in self.attributes:
            value = getattr(device, attribute, None)
            if value is not None:
                print("%s: %s" % (attribute, value))

        print()


def main():
    stream = os.popen(COMMAND)
    dmi = DmidecodeParser(stream)

    result = DmiResult()
    dmi.run(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
