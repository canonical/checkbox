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

from checkbox_support.parsers.meminfo import MeminfoParser


class MeminfoResult:

    def setMemory(self, memory):
        for key, value in sorted(memory.items()):
            print("%s: %s" % (key, value))


def main():
    parser = MeminfoParser()
    result = MeminfoResult()
    meminfo = parser.run()
    result.setMemory(meminfo)

    return 0


if __name__ == "__main__":
    sys.exit(main())
