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
from unittest.mock import patch, MagicMock
from pathlib import Path
from io import StringIO
import graphics_card_resource


class GraphicsCardResourceTests(unittest.TestCase):

    def _run_main_with_udev_data(self, udev_data):
        """Helper to run main() with mocked udev data."""
        with patch("graphics_card_resource.parse_args") as mock_args, \
             patch("graphics_card_resource.subprocess_lines_generator") as mock_gen, \
             patch("graphics_card_resource.sys.stderr", new_callable=StringIO) as mock_stderr, \
             patch("builtins.print"):

            mock_args.return_value = MagicMock(command="udev_resource.py")
            mock_gen.return_value = iter(udev_data)
            graphics_card_resource.main()
            return mock_stderr.getvalue()

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

    def test_drm_node_from_udev_name(self):
        """Test DRM node detection when name is in udev record."""
        udev_data = [
            "category: VIDEO",
            "path: /devices/pci0000:00/0000:00:02.0",
            "name: card0",
            ""
        ]

        def path_factory(path_str):
            mock_path = MagicMock(spec=Path)
            if path_str.startswith("/sys"):
                mock_path.glob.return_value = iter([])
            elif path_str == "/dev/":
                mock_result = MagicMock(spec=Path)
                mock_result.exists.return_value = True
                mock_path.__truediv__ = MagicMock(return_value=mock_result)
            return mock_path

        with patch("graphics_card_resource.Path", side_effect=path_factory):
            stderr = self._run_main_with_udev_data(udev_data)
        self.assertEqual(stderr, "")

    def test_drm_node_single_card_in_sysfs(self):
        """Test DRM node detection when exactly one card found in sysfs."""
        udev_data = [
            "category: VIDEO",
            "path: /devices/pci0000:00/0000:00:02.0",
            ""
        ]

        mock_card = MagicMock(spec=Path, name="card0")

        def path_factory(path_str):
            mock_path = MagicMock(spec=Path)
            if path_str.startswith("/sys"):
                mock_path.glob.return_value = iter([mock_card])
            elif path_str == "/dev/dri":
                mock_path.__truediv__ = MagicMock(return_value=MagicMock(spec=Path))
            return mock_path

        with patch("graphics_card_resource.Path", side_effect=path_factory):
            stderr = self._run_main_with_udev_data(udev_data)
        self.assertEqual(stderr, "")

    def test_drm_node_warning_no_cards(self):
        """Test DRM node detection when no cards found (warning case)."""
        udev_data = [
            "category: VIDEO",
            "path: /devices/pci0000:00/0000:00:02.0",
            ""
        ]

        def path_factory(path_str):
            mock_path = MagicMock(spec=Path)
            if path_str.startswith("/sys"):
                mock_path.glob.return_value = iter([])
            return mock_path

        with patch("graphics_card_resource.Path", side_effect=path_factory):
            stderr = self._run_main_with_udev_data(udev_data)
        self.assertIn("Warning: could not find DRM node", stderr)
        self.assertIn("/devices/pci0000:00/0000:00:02.0", stderr)

    def test_drm_node_warning_multiple_cards(self):
        """Test DRM node detection when multiple cards found (warning case)."""
        udev_data = [
            "category: VIDEO",
            "path: /devices/pci0000:00/0000:00:02.0",
            ""
        ]

        mock_card1 = MagicMock(spec=Path, name="card0")
        mock_card2 = MagicMock(spec=Path, name="card1")

        def path_factory(path_str):
            mock_path = MagicMock(spec=Path)
            if path_str.startswith("/sys"):
                mock_path.glob.return_value = iter([mock_card1, mock_card2])
            return mock_path

        with patch("graphics_card_resource.Path", side_effect=path_factory):
            stderr = self._run_main_with_udev_data(udev_data)
        self.assertIn("Warning: could not find DRM node", stderr)
        self.assertIn("/devices/pci0000:00/0000:00:02.0", stderr)


if __name__ == "__main__":
    unittest.main()
