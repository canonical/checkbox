#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import os
import time
from unittest.mock import patch, MagicMock, mock_open
from check_hardware_attributes import walk_devices, try_read_node


class TestSysfsScanner(unittest.TestCase):

    @patch("builtins.open", new_callable=mock_open, read_data="test_data")
    def test_try_read_node_success(self, mock_file):
        """Test that try_read_node successfully opens and reads a byte."""
        try_read_node("/fake/path")
        mock_file.assert_called_once_with("/fake/path", "r")
        mock_file().read.assert_called_once_with(1)

    @patch("builtins.open", side_effect=Exception("Read Error"))
    def test_try_read_node_handles_exception(self, mock_file):
        """Test that try_read_node catches and suppresses exceptions."""
        try:
            try_read_node("/fake/path")
        except Exception as e:
            self.fail("try_read_node raised {} unexpectedly!".format(e))

    @patch("os.walk")
    @patch("os.access")
    @patch("multiprocessing.Process")
    def test_walk_devices_skips_noisy_files(
        self, mock_process, mock_access, mock_walk
    ):
        """Verify that uevent, modalias, and resource are ignored."""
        # Mocking os.walk to return a few files, including an excluded one
        mock_walk.return_value = [
            ("/sys/devices", ("dir1",), ("uevent", "valid_node"))
        ]
        mock_access.return_value = True

        walk_devices("/sys/devices", timeout=0.1)

        # Ensure Process was only called for 'valid_node', not 'uevent'
        self.assertEqual(mock_process.call_count, 1)
        _, args = mock_process.call_args
        self.assertIn("valid_node", args["args"][0])

    @patch("os.walk")
    @patch("os.access")
    @patch("multiprocessing.Process")
    def test_walk_devices_skips_unreadable_files(
        self, mock_process, mock_access, mock_walk
    ):
        """Verify that files without read access are ignored."""
        # Mocking os.walk to return a file
        mock_walk.return_value = [("/sys/devices", (), ("restricted_node",))]

        # Simulate os.access returning False (No Read Permission)
        mock_access.return_value = False

        result = walk_devices("/sys/devices", timeout=0.1)

        # Ensure Process was NEVER called because access was denied
        self.assertEqual(mock_process.call_count, 0)
        # Ensure result is success (0) because no hangs occurred
        self.assertEqual(result, False)

    @patch("os.walk")
    @patch("os.access")
    @patch("multiprocessing.Process")
    def test_walk_devices_detects_hang(
        self, mock_process, mock_access, mock_walk
    ):
        """Simulate a subprocess hang and ensure failed status is returned."""
        mock_walk.return_value = [("/sys/devices", (), ("stuck_node",))]
        mock_access.return_value = True

        # Create a mock process that appears alive after joining
        instance = mock_process.return_value
        instance.is_alive.return_value = True

        # Test walk_devices
        with patch("builtins.print") as mock_print:
            result = walk_devices("/sys/devices", timeout=0.1)

            # Verify status is failed (1) and path was printed
            self.assertEqual(result, True)
            mock_print.assert_called_with(
                "/sys/devices/stuck_node read timeout"
            )

    @patch("os.walk")
    @patch("os.access")
    @patch("multiprocessing.Process")
    def test_walk_devices_success_path(
        self, mock_process, mock_access, mock_walk
    ):
        """Ensure result is 0 when all processes finish within timeout."""
        mock_walk.return_value = [("/sys/devices", (), ("healthy_node",))]
        mock_access.return_value = True

        instance = mock_process.return_value
        instance.is_alive.return_value = False

        result = walk_devices("/sys/devices", timeout=1.0)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
