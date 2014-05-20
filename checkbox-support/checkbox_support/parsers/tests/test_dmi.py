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


class DmiResult(object):

    def __init__(self):
        self.devices = []

    def addDmiDevice(self, device):
        self.devices.append(device)

    def getDevice(self, category):
        for device in self.devices:
            if device.category == category:
                return device

        return None


class TestDmiMixin(object):

    def getParser(self):
        raise NotImplementedError()

    def getResult(self):
        parser = self.getParser()
        result = DmiResult()
        parser.run(result)
        return result

    def test_devices(self):
        result = self.getResult()
        self.assertEqual(len(result.devices), 4)

    def test_bios(self):
        result = self.getResult()
        device = result.getDevice("BIOS")
        self.assertTrue(device)
        self.assertEqual(device.product, "BIOS PRODUCT")
        self.assertEqual(device.vendor, "BIOS VENDOR")
        self.assertEqual(device.serial, None)

    def test_board(self):
        result = self.getResult()
        device = result.getDevice("BOARD")
        self.assertTrue(device)
        self.assertEqual(device.product, None)
        self.assertEqual(device.vendor, None)
        self.assertEqual(device.serial, None)

    def test_chassis(self):
        result = self.getResult()
        device = result.getDevice("CHASSIS")
        self.assertTrue(device)
        self.assertEqual(device.product, "Notebook")
        self.assertEqual(device.vendor, "CHASSIS VENDOR")
        self.assertEqual(device.serial, None)

    def test_system(self):
        result = self.getResult()
        device = result.getDevice("SYSTEM")
        self.assertTrue(device)
        self.assertEqual(device.product, "SYSTEM PRODUCT")
        self.assertEqual(device.vendor, "SYSTEM VENDOR")
        self.assertEqual(device.serial, "SYSTEM SERIAL")
