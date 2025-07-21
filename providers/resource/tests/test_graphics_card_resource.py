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
from unittest.mock import patch
import graphics_card_resource


class GraphicsCardResourceTests(unittest.TestCase):

    @patch("graphics_card_resource.get_release_info")
    def test_compare_ubuntu_release_version(self, mock_release_info):
        mock_release_info.return_value = {"release": "24.04"}
        result = graphics_card_resource.compare_ubuntu_release_version("22.04")
        self.assertTrue(result)

        mock_release_info.return_value = {"release": "22.04"}
        result = graphics_card_resource.compare_ubuntu_release_version("24.04")
        self.assertFalse(result)

    @patch(
        "packaging.version.parse",
        side_effect=ImportError("Cannot import version"),
    )
    @patch("graphics_card_resource.get_release_info")
    def test_compare_ubuntu_release_version_with_import_error(
        self, mock_release_info, mock_version
    ):
        mock_release_info.return_value = {"release": "24.04"}
        result = graphics_card_resource.compare_ubuntu_release_version("22.04")
        self.assertTrue(result)

        mock_release_info.return_value = {"release": "22.04"}
        result = graphics_card_resource.compare_ubuntu_release_version("24.04")
        self.assertFalse(result)

    def test_udev_devices_success(self):
        record_line = ["path: /devices/pci0000:00/0000:00:02.1/0000:01:00.0"]
        record = graphics_card_resource.udev_devices(record_line)
        record_list = list(record)
        self.assertEqual(len(record_list), 1)
        self.assertEqual(record_list[0]["pci_device_name"], "0000:01:00.0")


if __name__ == "__main__":
    unittest.main()
