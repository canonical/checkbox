#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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

# pylint: disable=protected-access

import unittest
import io
import sys
from unittest.mock import patch, MagicMock

from camera_test import CameraTest, v4l2_capability


@patch("builtins.print", new=MagicMock())
class CameraTestTests(unittest.TestCase):
    """This class provides test cases for the CameraTest class."""

    def setUp(self):
        self.camera_instance = CameraTest(None)

    @patch("camera_test.CameraTest._supported_resolutions_to_string")
    @patch("camera_test.CameraTest._get_supported_resolutions")
    def test_detect_and_show_camera_info_with_single_planar_capture_capability(
        self,
        mock_get_supported_resolutions,
        mock_supported_resolutions_to_string,
    ):
        """Test camera device supports the single planar capture capabilitiy"""
        mock_get_supported_resolutions.return_value = [
            {
                "description": "fake",
                "pixelformat": "fake",
                "resolutions": [[123, 987]],
            }
        ]
        mock_supported_resolutions_to_string.return_value = "Resolutions: fake"

        fake_device = "/dev/video0"
        fake_v4l2_capability = v4l2_capability()
        fake_v4l2_capability.card = b"fake card"
        fake_v4l2_capability.driver = b"fake driver"
        fake_v4l2_capability.version = 123
        fake_v4l2_capability.capabilities = 0x1
        result = self.camera_instance._detect_and_show_camera_info(
            fake_device, fake_v4l2_capability
        )
        self.assertEqual(0, result)

    @patch("camera_test.CameraTest._supported_resolutions_to_string")
    @patch("camera_test.CameraTest._get_supported_resolutions")
    def test_detect_and_show_camera_info_with_multi_planar_capture_capability(
        self,
        mock_get_supported_resolutions,
        mock_supported_resolutions_to_string,
    ):
        """Test camera device supports the multi planar capture capabilitiy"""
        mock_get_supported_resolutions.return_value = [
            {
                "description": "fake",
                "pixelformat": "fake",
                "resolutions": [[123, 987]],
            }
        ]
        mock_supported_resolutions_to_string.return_value = "Resolutions: fake"

        fake_device = "/dev/video0"
        fake_v4l2_capability = v4l2_capability()
        fake_v4l2_capability.card = b"fake card"
        fake_v4l2_capability.driver = b"fake driver"
        fake_v4l2_capability.version = 123
        fake_v4l2_capability.capabilities = 0x00001000
        result = self.camera_instance._detect_and_show_camera_info(
            fake_device, fake_v4l2_capability
        )
        self.assertEqual(0, result)

    @patch("camera_test.CameraTest._supported_resolutions_to_string")
    @patch("camera_test.CameraTest._get_supported_resolutions")
    def test_detect_and_show_camera_info_without_capture_capability(
        self,
        mock_get_supported_resolutions,
        mock_supported_resolutions_to_string,
    ):
        """Test camera device doesn't support the capture capabilitiy"""
        mock_get_supported_resolutions.return_value = [
            {
                "description": "YUYV",
                "pixelformat": "YUYV",
                "resolutions": [[640, 480]],
            }
        ]
        mock_supported_resolutions_to_string.return_value = "Resolutions: fake"

        fake_device = "/dev/video0"
        fake_v4l2_capability = v4l2_capability()
        fake_v4l2_capability.card = b"fake card"
        fake_v4l2_capability.driver = b"fake driver"
        fake_v4l2_capability.version = 123
        fake_v4l2_capability.capabilities = 0x000010000
        result = self.camera_instance._detect_and_show_camera_info(
            fake_device, fake_v4l2_capability
        )
        self.assertEqual(1, result)

    def tearDown(self):
        # release stdout
        sys.stdout = sys.__stdout__
