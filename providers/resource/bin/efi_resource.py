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

from checkbox_support.parsers.efi import EfiParser


# Command to retrieve efi information.
COMMAND = (
    "[ -d /sys/firmware/efi ] && cat /var/log/kern.log* | "
    "grep -m 1 -o --color=never 'EFI v.*' || true"
)


class EfiResult:

    attributes = (
        "path",
        "category",
        "product",
        "vendor",
    )

    def setEfiDevice(self, device):
        for attribute in self.attributes:
            value = getattr(device, attribute, None)
            if value is not None:
                print("%s: %s" % (attribute, value))

        print()


def main():
    stream = os.popen(COMMAND)
    efi = EfiParser(stream)

    result = EfiResult()
    efi.run(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
