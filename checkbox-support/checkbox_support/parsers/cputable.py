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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re


CPUTABLE_RE = re.compile(
    r"^(?!\#)(?P<debian_name>\S+)"
    r"\s+(?P<gnu_name>\S+)"
    r"\s+(?P<regex>\S+)"
    r"\s+(?P<bits>\d+)"
    r"\s+(?P<endianness>big|little)")


class CputableParser(object):
    """Parser for the /usr/share/dpkg/cputable file."""

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        for line in self.stream.readlines():
            match = CPUTABLE_RE.match(line)
            if match:
                cpu = match.groupdict()
                cpu["bits"] = int(cpu["bits"])
                result.addCpu(cpu)
