#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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

from io import StringIO
from unittest import TestCase

from checkbox_support.parsers.efi import EfiParser


class EfiResult(object):

    def __init__(self):
        self.device = None

    def setEfiDevice(self, device):
        self.device = device


class TestCputableParser(TestCase):

    def getParser(self, string):
        stream = StringIO(string)
        return EfiParser(stream)

    def getResult(self, string):
        parser = self.getParser(string)
        result = EfiResult()
        parser.run(result)
        return result

    def test_empty(self):
        result = self.getResult("")
        self.assertEqual(result.device, None)

    def test_product(self):
        result = self.getResult("""
Foo Bar
""")
        self.assertEqual(result.device.vendor, None)
        self.assertEqual(result.device.product, "Foo Bar")

    def test_vendor_product(self):
        result = self.getResult("""
Product by Vendor
""")
        self.assertEqual(result.device.vendor, "Vendor")
        self.assertEqual(result.device.product, "Product")
