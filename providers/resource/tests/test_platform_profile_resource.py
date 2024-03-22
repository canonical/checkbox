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

""" A unittest module for the platform_profile_resource module. """
import unittest
from unittest.mock import patch
import platform_profile_resource


class TestPlatformProfilesSupport(unittest.TestCase):
    """ Test the platform profile support """
    @patch("builtins.print")
    def test_supported(self, mock_print):
        """ Test the function when all paths exist"""
        with patch("pathlib.Path.exists") as mock_exists:
            # All paths exist
            mock_exists.side_effect = [True, True, True]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_once_with("supported: True")

    @patch("builtins.print")
    def test_unsupported(self, mock_print):
        """ Test the function when some paths do not exist"""
        with patch("pathlib.Path.exists") as mock_exists:
            # First scenario: None of the paths exist
            mock_exists.side_effect = [False, False, False]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_once_with("supported: False")

            # Second scenario: Only sysfs_root exists
            mock_exists.side_effect = [True, False, False]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_with("supported: False")
            self.assertEqual(mock_print.call_count, 2)

            # Third scenario: sysfs_root and choices_path exist,
            # but profile_path does not exist
            mock_exists.side_effect = [True, True, False]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_with("supported: False")
            self.assertEqual(mock_print.call_count, 3)

            # Fourth scenario: sysfs_root and profile_path exist,
            # but choices_path does not exist
            mock_exists.side_effect = [True, False, True]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_with("supported: False")
            self.assertEqual(mock_print.call_count, 4)

    @patch("platform_profile_resource.check_platform_profiles")
    def test_main(self, mock_check_platform_profiles):
        """ Test the main function """
        platform_profile_resource.main()
        mock_check_platform_profiles.assert_called()
