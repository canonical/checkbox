#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2009-2025 Canonical Ltd.
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

from checkbox_support.helpers.release_info import get_release_info
import sys


def main():
    release_info = get_release_info()
    for key, value in release_info.items():
        print("%s: %s" % (key, value))


if __name__ == "__main__":
    sys.exit(main())
