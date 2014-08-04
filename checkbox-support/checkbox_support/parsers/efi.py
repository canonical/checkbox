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


class EfiDevice(object):

    path = "/sys/class/dmi/id/bios_version"
    category = "EFI"

    def __init__(self, product, vendor=None):
        self.product = product
        self.vendor = vendor


class EfiParser(object):
    """Parser for EFI information."""

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        vendor_product_pattern = re.compile(
            r"^(?P<product>.*)\s+by\s+(?P<vendor>.*)$")

        for line in self.stream.readlines():
            line = line.strip()
            match = vendor_product_pattern.match(line)
            if match:
                product = match.group("product")
                vendor = match.group("vendor")
                device = EfiDevice(product, vendor)
            else:
                device = EfiDevice(line)

            result.setEfiDevice(device)
