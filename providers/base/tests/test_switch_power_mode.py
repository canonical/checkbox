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

""" A unittest module for the switch_power_mode module. """
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import io

from switch_power_mode import get_sysfs_content, set_power_profile, main


class TestSwitchPowerMode(unittest.TestCase):
    """Tests for the switch_power_mode module."""

    @patch("builtins.open")  # Mock the open function
    def test_get_sysfs_content_success(self, mock_open):
        """
        Tests successful reading of sysfs file content.
        """
        mock_file = MagicMock(spec=io.TextIOWrapper)
        mock_file.read.return_value = "low-power balanced performance"
        mock_open.return_value.__enter__.return_value = mock_file

        content = get_sysfs_content(Path("/fake/path/power_profile_choices"))

        self.assertEqual(content, "low-power balanced performance")
        mock_open.assert_called_once_with(
            Path("/fake/path/power_profile_choices"), "rt", encoding="utf-8"
        )

    @patch("switch_power_mode.open")  # Mock the open function
    def test_get_sysfs_content_failure(self, mock_open):
        """
        Tests handling of an empty sysfs file.
        """
        mock_file = MagicMock(spec=io.TextIOWrapper)
        mock_file.read.return_value = ""
        mock_open.return_value.__enter__.return_value = mock_file

        with self.assertRaises(SystemExit) as cm:
            get_sysfs_content(Path("/fake/path/power_profile"))

        self.assertEqual(
            str(cm.exception),
            "Failed to read sysfs file: /fake/path/power_profile",
        )
        mock_open.assert_called_once_with(
            Path("/fake/path/power_profile"), "rt", encoding="utf-8"
        )

    @patch("subprocess.check_call")  # Mock the subprocess.check_call function
    def test_set_power_profile_success(self, mock_check_call):
        """
        Tests successful setting of the power profile.
        """
        set_power_profile("balanced")

        mock_check_call.assert_called_once_with(
            ["powerprofilesctl", "set", "balanced"]
        )

    @patch("subprocess.check_call")  # Mock the subprocess.check_call function
    def test_set_power_profile_low_power(self, mock_check_call):
        """
        Tests conversion of "low-power" to "power-saver" before setting.
        """
        set_power_profile("low-power")

        mock_check_call.assert_called_once_with(
            ["powerprofilesctl", "set", "power-saver"]
        )

    @patch("subprocess.check_call")  # Mock the subprocess.check_call function
    def test_set_power_profile_failure(self, mock_check_call):
        """
        Tests handling of a failed power profile setting.
        """
        mock_check_call.side_effect = subprocess.CalledProcessError(
            1, "powerprofilesctl"
        )

        with self.assertRaises(SystemExit) as cm:
            set_power_profile("performance")

        self.assertEqual(
            str(cm.exception), "Failed to set power mode to performance."
        )
        mock_check_call.assert_called_once_with(
            ["powerprofilesctl", "set", "performance"]
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_main_success(self, mock_stdout):
        """
        Tests successful execution of the main function.
        """
        with patch(
            "switch_power_mode.get_sysfs_content"
        ) as mock_get_sysfs_content, patch(
            "switch_power_mode.set_power_profile"
        ) as mock_set_power_profile:
            mock_get_sysfs_content.side_effect = [
                "balanced",
                "low-power balanced performance",
                "low-power",
                "balanced",
                "performance",
            ]
            mock_set_power_profile.side_effect = [None, None, None, None]

            # Call the main function
            main()

            expected_output = """\
Power mode choices: ['low-power', 'balanced', 'performance']
Switch to low-power successfully.
Switch to balanced successfully.
Switch to performance successfully.
"""
            self.assertEqual(mock_stdout.getvalue(), expected_output)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("switch_power_mode.get_sysfs_content")
    @patch("switch_power_mode.set_power_profile")
    def test_main_failure(
        self, mock_set_power_profile, mock_get_sysfs_content, mock_stdout
    ):
        """
        Tests failed execution of the main function.
        """
        mock_get_sysfs_content.side_effect = [
            "balanced",
            "low-power balanced performance",
            "low-power",
            "low-power",
        ]
        mock_set_power_profile.side_effect = [
            "lower-power",
            "balanced",
            "performance",
            None,
        ]

        # Call the function and check if SystemExit is raised
        with self.assertRaises(SystemExit) as cm:
            main()

        # Assertions
        self.assertEqual(
            cm.exception.code, "ERROR: Failed to switch power mode to balanced"
        )
        expected_output = """\
Power mode choices: ['low-power', 'balanced', 'performance']
Switch to low-power successfully.
"""
        self.assertEqual(mock_stdout.getvalue(), expected_output)


if __name__ == "__main__":
    unittest.main()
