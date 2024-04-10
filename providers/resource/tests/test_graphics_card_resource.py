#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
#    Authors: Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

import unittest
from graphics_card_resource import *


class UdevDevicesTests(unittest.TestCase):
    record_line = ["path: /devices/pci0000:00/0000:00:02.1/0000:01:00.0"]

    def test_success(self):
        record = udev_devices(self.record_line)
        record_list = list(record)
        self.assertEqual(len(record_list), 1)
        self.assertEqual(record_list[0]["pci_device_name"], "0000:01:00.0")


if __name__ == "__main__":
    unittest.main()
