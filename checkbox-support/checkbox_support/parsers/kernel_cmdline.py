# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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
        result.setKernelCmdline(line)
