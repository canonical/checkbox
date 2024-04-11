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
import re
import sys

from subprocess import (
    Popen,
    PIPE,
)


# Command to retrieve dpkg information.
COMMAND = "dpkg --version"


def get_dpkg():
    dpkg = {}
    output = Popen(COMMAND, stdout=PIPE, shell=True).communicate()[0]
    match = re.search(
        r"(?P<version>[\d\.]+) \((?P<architecture>.*)\)",
        output.decode(encoding="utf-8"),
    )
    if match:
        dpkg["version"] = match.group("version")
        dpkg["architecture"] = match.group("architecture")

    return dpkg


def main():
    dpkg = get_dpkg()

    for key, value in dpkg.items():
        print("%s: %s" % (key, value))

    return 0


if __name__ == "__main__":
    sys.exit(main())
