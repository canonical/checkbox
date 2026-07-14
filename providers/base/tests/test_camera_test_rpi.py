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

import sys
import unittest
from unittest.mock import MagicMock, call, patch

sys.modules["picamera"] = MagicMock()
from camera_test_rpi import main, capture, test_res  # noqa: E402


class CameraTestRPITests(unittest.TestCase):
    """Test cases for the camera_test_rpi module."""

    @patch("builtins.print", MagicMock())
    @patch("camera_test_rpi.time.sleep", MagicMock())
    @patch("camera_test_rpi.os.path")
    @patch("camera_test_rpi.picamera.PiCamera")
    def test_capture(self, mock_picamera, mock_path):
        mock_path.expandvars.return_value = "/tmp/session"
        mock_path.join.side_effect = [
            "/tmp/session/picam_{}_vchiq.jpg".format(i)
            for i in range(1, len(test_res) + 2)
        ]

        capture("/dev/vchiq")

        # Verify the camera calls
        expected_picamera_calls = [
            call(resolution=res, framerate=fr) for res, fr in test_res
        ]
        self.assertEqual(mock_picamera.call_count, len(test_res))
        self.assertEqual(mock_picamera.call_args_list, expected_picamera_calls)

        # Verify the capture calls
        expected_capture_calls = [
            call("/tmp/session/picam_{}_{}.jpg".format(index, "vchiq"))
            for index in range(1, len(test_res) + 1)
        ]
        camera = mock_picamera.return_value.__enter__.return_value
        camera.capture.assert_has_calls(expected_capture_calls)

    @patch("camera_test_rpi.capture")
    def test_main_passes_device(self, mock_capture):
        sys.argv = ["camera_test_rpi.py", "--device", "/dev/video0"]
        main()
        mock_capture.assert_called_once_with("/dev/video0")

    @patch("camera_test_rpi.capture")
    def test_main_default_device(self, mock_capture):
        sys.argv = ["camera_test_rpi.py"]
        main()
        mock_capture.assert_called_once_with("/dev/vchiq")
