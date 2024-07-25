#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Bin Li <bin.li@canonical.com>
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

# pylint: disable=import-error

""" A unittest module for the check_power_mode module. """
import unittest
from unittest.mock import patch
import io

from check_power_mode import main


class TestCheckPowerMode(unittest.TestCase):
    """Tests for the check_power_mode module."""

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("check_power_mode.get_sysfs_content")
    def test_main_success(self, mock_get_sysfs_content, mock_stdout):
        """
        Tests successful execution of the main function.
        """
        mock_get_sysfs_content.return_value = "balanced"

        # Call the main function
        main()

        self.assertEqual(mock_stdout.getvalue(), "balanced\n")

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("check_power_mode.get_sysfs_content")
    def test_main_failure(self, mock_get_sysfs_content, mock_stdout):
        """
        Tests failed execution of the main function.
        """
        mock_get_sysfs_content.return_value = ""

        main()

        self.assertNotEqual(mock_stdout.getvalue(), "balanced\n")


if __name__ == "__main__":
    unittest.main()
