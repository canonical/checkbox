#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2011-2025 Canonical Ltd.
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


def sane_product(og_product: str) -> str:
    """
    Transform the product key into a usable form

    The product key is basically free-form text. In order to make it more
    usable in resource expressions, which usually want to know if a device is
    portable (a laptop/tablet) or not, this cleans up the key to a "canonical"
    answer, either `non-portable` or `portable`
    """
    cleaned = og_product.lower().replace(" ", "-")
    if cleaned in [
        "desktop",
        "low-profile-desktop",
        "tower",
        "mini-tower",
        "space-saving",
        "all-in-one",
        "aio",
        "mini-pc",
        "main-server-chassis",
    ]:
        return "non-portable"
    elif cleaned in [
        "notebook",
        "laptop",
        "portable",
        "convertible",
        "tablet",
        "detachable",
    ]:
        return "portable"
    return "unknown"


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
                print("{}: {}".format(attribute, value))
            if attribute == "product" and value:
                print("{}: {}".format("sane_product", sane_product(value)))

        print()


def main():
    stream = os.popen(COMMAND)
    dmi = DmidecodeParser(stream)

    result = DmiResult()
    dmi.run(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
