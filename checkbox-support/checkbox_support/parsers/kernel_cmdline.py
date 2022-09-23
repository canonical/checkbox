# This file is part of Checkbox.
#
# Copyright 2015-2019 Canonical Ltd.
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

import io


class KernelCmdlineResult():

    def __init__(self):
        self.flags = []
        self.params = {}

    def addFlag(self, flag):
        self.flags.append(flag)

    def addParam(self, name, val):
        self.params[name] = val


class KernelCmdlineParser(object):

    """Parser for kernel cmdline information."""

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """
        The kernel cmdline is usually a single line of text so this parser is
        quite simple. It will just call the result's setKernelCmdline method
        with the first line
        """
        line = self.stream.readline().strip()
        for entry in line.split():
            if '=' in entry:
                for name in entry.split('=')[:-1]:
                    result.addParam(name, entry.split('=')[-1])
                continue
            result.addFlag(entry)


def parse_kernel_cmdline(cmdline):
    stream = io.StringIO(cmdline)
    parser = KernelCmdlineParser(stream)
    result = KernelCmdlineResult()
    parser.run(result)
    return result
