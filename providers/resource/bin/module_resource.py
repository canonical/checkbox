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


# Filename where cpuinfo is stored.
MODULES_FILENAME = "/proc/modules"


def get_module(line):
    """
    Each line consists of the following information for each module:

    name:         Name of the module.
    size:         Memory size of the module, in bytes.
    instances:    How many instances of the module are currently loaded.
    dependencies: If the module depends upon another module to be present
                  in order to function, and lists those modules.
    state:        The load state of the module: Live, Loading or Unloading.
    offset:       Current kernel memory offset for the loaded module.
    """
    (name, size, instances, dependencies, state, offset) = line.split(" ")[:6]
    if dependencies == "-":
        dependencies = ""

    return {
        "name": name,
        "size": int(size),
        "instances": int(instances),
        "dependencies": dependencies.replace(",", " ").strip(),
        "state": state,
        "offset": int(offset, 16),
    }


def get_modules(filename):
    file = open(filename, "r")
    for line in file.readlines():
        line = line.strip()
        if line:
            yield get_module(line)


def main():
    modules = get_modules(MODULES_FILENAME)
    for module in modules:
        for key, value in module.items():
            if value != "":
                print("%s: %s" % (key, value))

        # Empty line
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
