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
import re


class MeminfoParser:
    """Parser for the /proc/meminfo file."""

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        key_value_pattern = re.compile(r"(?P<key>.*):\s+(?P<value>.*)")
        meminfo_map = {
            "MemTotal": "total",
            "SwapTotal": "swap"}

        meminfo = {}
        for line in self.stream.readlines():
            line = line.strip()
            match = key_value_pattern.match(line)
            if match:
                key = match.group("key")
                if key in meminfo_map:
                    key = meminfo_map[key]
                    value = match.group("value")
                    (integer, factor) = value.split()
                    meminfo[key] = int(integer) * 1024

        result.setMemory(meminfo)
