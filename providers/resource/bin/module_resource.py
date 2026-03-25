#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2009 Canonical Ltd.
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
import sys
from checkbox_ng.support.device_info import get_kernel_modules


def main():
    modules = get_kernel_modules()
    for module in modules:
        for key, value in module.items():
            if value != "":
                print("%s: %s" % (key, value))

        # Empty line
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
