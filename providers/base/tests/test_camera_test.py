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

import argparse
import errno
import logging
import unittest
import sys
from unittest.mock import patch, MagicMock

from camera_test import (
    CameraTest,
    v4l2_capability,
    V4L2_FRMSIZE_TYPE_DISCRETE,
    V4L2_FRMSIZE_TYPE_STEPWISE,
    parse_arguments,
)


@patch("builtins.print", new=MagicMock())
class CameraTestTests(unittest.TestCase):
    """This class provides test cases for the CameraTest class."""

    def setUp(self):
        self.camera_instance = CameraTest(None)

    def test_supported_formats_to_string(self):
        formats = [
            {
                "pixelformat": "YUYV",
                "description": "YUYV",
                "resolutions": [[640, 480], [320, 240]],
            },
            {
                "pixelformat": "fake",
                "description": "fake",
                "resolutions": [[640, 480]],
            },
        ]
        expected_str = (
            "Format: YUYV (YUYV)\n"
            "Resolutions: 640x480,320x240\n"
            "Format: fake (fake)\n"
            "Resolutions: 640x480\n"
        )
        return_str = self.camera_instance._supported_formats_to_string(formats)
        self.assertEqual(return_str, expected_str)

    @patch("tempfile.NamedTemporaryFile", MagicMock())
    def test_resolutions(self):
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = [
            {
                "pixelformat": "YUYV",
                "description": "YUYV",
                "resolutions": [[640, 480], [320, 240]],
            }
        ]
        mock_camera._validate_image.return_value = True

        self.assertEqual(CameraTest.resolutions(mock_camera), 0)

        self.assertEqual(mock_camera._get_supported_formats.call_count, 1)
        self.assertEqual(
            mock_camera._supported_formats_to_string.call_count, 1
        )
        self.assertEqual(mock_camera._save_debug_image.call_count, 1)
        self.assertEqual(mock_camera._still_helper.call_count, 2)
        self.assertEqual(mock_camera._validate_image.call_count, 2)

        # Test that the function also works with no output
        mock_camera.args.output = None
        self.assertEqual(CameraTest.resolutions(mock_camera), 0)

    @patch("tempfile.NamedTemporaryFile", MagicMock())
    def test_resolutions_wrong_validation(self):
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = [
            {
                "pixelformat": "YUYV",
                "description": "YUYV",
                "resolutions": [[640, 480], [320, 240]],
            }
        ]
        mock_camera._validate_image.return_value = False

        self.assertEqual(CameraTest.resolutions(mock_camera), 1)

    def test_resolutions_no_formats(self):
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = []

        with self.assertRaises(SystemExit):
            CameraTest.resolutions(mock_camera)

    @patch("camera_test.os.path.exists")
    def test_save_debug_image(self, mock_exists):
        mock_exists.return_value = True
        mock_camera = MagicMock()
        format = {
            "pixelformat": "YUYV",
            "description": "YUYV",
            "resolutions": [[640, 480], [320, 240]],
        }
        CameraTest._save_debug_image(
            mock_camera, format, "/dev/video0", "/tmp"
        )
        self.assertEqual(mock_camera._still_helper.call_count, 1)

    @patch("camera_test.os.path.exists")
    def test_save_debug_image_fails_if_path_not_exists(self, mock_exists):
        mock_exists.return_value = False
        mock_camera = MagicMock()
        format = {
            "pixelformat": "YUYV",
            "description": "YUYV",
            "resolutions": [[640, 480], [320, 240]],
        }
        with self.assertRaises(SystemExit):
            CameraTest._save_debug_image(
                mock_camera, format, "/dev/video0", "/tmp"
            )

    def ioctl_enum_format_side_effect(self, fd, request, fmt):
        # Define format details based on the index
        formats = [
            (b"YUV 4:2:2", 0x56595559),
            (b"YUV 4:2:0", 0x3231564E),
        ]
        if fmt.index < len(formats):
            fmt.description, fmt.pixelformat = formats[fmt.index]
            return 0  # Success
        else:
            raise IOError(errno.EINVAL, "No more formats")

    @patch("fcntl.ioctl")
    @patch("builtins.open", MagicMock())
    def test_get_supported_pixel_formats(self, mock_ioctl):
        mock_ioctl.side_effect = self.ioctl_enum_format_side_effect

        expected_pixel_formats = [
            {
                "pixelformat": "YUYV",
                "pixelformat_int": 1448695129,
                "description": "YUV 4:2:2",
            },
            {
                "pixelformat": "NV12",
                "pixelformat_int": 842094158,
                "description": "YUV 4:2:0",
            },
        ]

        pixel_formats = CameraTest._get_supported_pixel_formats(
            MagicMock(), "/dev/video0", 5
        )
        self.assertEqual(pixel_formats, expected_pixel_formats)

    @patch("fcntl.ioctl")
    @patch("builtins.open", MagicMock())
    def test_get_supported_pixel_formats_max_formats(self, mock_ioctl):
        mock_ioctl.side_effect = self.ioctl_enum_format_side_effect
        expected_pixel_formats = [
            {
                "pixelformat": "YUYV",
                "pixelformat_int": 1448695129,
                "description": "YUV 4:2:2",
            }
        ]
        pixel_formats = CameraTest._get_supported_pixel_formats(
            MagicMock(), "/dev/video0", 1
        )
        self.assertEqual(pixel_formats, expected_pixel_formats)

    @patch("fcntl.ioctl")
    @patch("builtins.open", MagicMock())
    def test_get_supported_pixel_formats_unexpected_error(self, mock_ioctl):
        mock_ioctl.side_effect = IOError(errno.EIO, "Unexpected error")
        pixel_formats = CameraTest._get_supported_pixel_formats(
            MagicMock(), "/dev/video0", 5
        )
        self.assertEqual(pixel_formats, [])

    # def _get_supported_formats(self, device):
    #     """
    #     Query the camera for supported format info for a given pixel_format.
    #     Data is returned in a list of dictionaries with supported pixel
    #     formats as the following example shows:
    #     format_info['pixelformat'] = "YUYV"
    #     format_info['description'] = "(YUV 4:2:2 (YUYV))"
    #     format_info['resolutions'] = [[width, height], [640, 480], [1280, 720]]

    #     If we are unable to gather any information from the driver, then we
    #     return YUYV and 640x480 which seems to be a safe default.
    #     Per the v4l2 spec the ioctl used here is experimental
    #     but seems to be well supported.
    #     """
    #     supported_formats_info = self._get_supported_pixel_formats(device)

    #     # If we can't get any formats, we will return YUYV and 640x480
    #     if not supported_formats_info:
    #         format_info = {}
    #         format_info["description"] = "YUYV"
    #         format_info["pixelformat"] = "YUYV"
    #         format_info["resolutions"] = [[640, 480]]
    #         return [format_info]

    #     for supported_format in supported_formats_info:
    #         resolutions = []
    #         framesize = v4l2_frmsizeenum()
    #         framesize.index = 0
    #         framesize.pixel_format = supported_format["pixelformat_int"]
    #         with open(device, "r") as vd:
    #             try:
    #                 while (
    #                     fcntl.ioctl(vd, VIDIOC_ENUM_FRAMESIZES, framesize) == 0
    #                 ):
    #                     if framesize.type == V4L2_FRMSIZE_TYPE_DISCRETE:
    #                         resolutions.append(
    #                             [
    #                                 framesize.discrete.width,
    #                                 framesize.discrete.height,
    #                             ]
    #                         )
    #                     # for continuous and stepwise, let's just use min and
    #                     # max they use the same structure and only return
    #                     # one result
    #                     elif framesize.type in (
    #                         V4L2_FRMSIZE_TYPE_CONTINUOUS,
    #                         V4L2_FRMSIZE_TYPE_STEPWISE,
    #                     ):
    #                         resolutions.append(
    #                             [
    #                                 framesize.stepwise.min_width,
    #                                 framesize.stepwise.min_height,
    #                             ]
    #                         )
    #                         resolutions.append(
    #                             [
    #                                 framesize.stepwise.max_width,
    #                                 framesize.stepwise.max_height,
    #                             ]
    #                         )
    #                         break
    #                     framesize.index = framesize.index + 1
    #             except IOError as e:
    #                 # EINVAL is the ioctl's way of telling us that there are no
    #                 # more formats, so we ignore it
    #                 if e.errno != errno.EINVAL:
    #                     print(
    #                         "Unable to determine supported framesizes "
    #                         "(resolutions), this may be a driver issue."
    #                     )
    #         supported_format["resolutions"] = resolutions
    #     return supported_formats_info

    def ioctl_enum_framesizes_side_effect(self, fd, request, fmt):
        if fmt.pixel_format == 1448695129:  # YUYV
            if fmt.index == 0:
                fmt.type = V4L2_FRMSIZE_TYPE_DISCRETE
                fmt.discrete.width = 640
                fmt.discrete.height = 480
            elif fmt.index == 1:
                fmt.type = V4L2_FRMSIZE_TYPE_DISCRETE
                fmt.discrete.width = 1280
                fmt.discrete.height = 720
            else:
                raise IOError(errno.EINVAL, "No more frame sizes")
        elif fmt.pixel_format == 842094158:  # NV12
            if fmt.index == 0:
                fmt.type = V4L2_FRMSIZE_TYPE_STEPWISE
                fmt.stepwise.min_width = 320
                fmt.stepwise.min_height = 240
                fmt.stepwise.max_width = 640
                fmt.stepwise.max_height = 480
            else:
                raise IOError(errno.EINVAL, "No more frame sizes")
        return 0

    @patch("fcntl.ioctl")
    def test_get_supported_formats(self, mock_ioctl):
        mock_camera = MagicMock()
        mock_camera._get_supported_pixel_formats.return_value = [
            {
                "pixelformat": "YUYV",
                "pixelformat_int": 1448695129,
                "description": "YUV 4:2:2",
            },
            {
                "pixelformat": "NV12",
                "pixelformat_int": 842094158,
                "description": "YUV 4:2:0",
            },
        ]
        mock_ioctl.side_effect = self.ioctl_enum_framesizes_side_effect

        expected_formats = [
            {
                "pixelformat": "YUYV",
                "pixelformat_int": 1448695129,
                "description": "YUV 4:2:2",
                "resolutions": [[640, 480], [1280, 720]],
            },
            {
                "pixelformat": "NV12",
                "description": "YUV 4:2:0",
                "pixelformat_int": 842094158,
                "resolutions": [[320, 240], [640, 480]],
            },
        ]

        with patch("builtins.open", MagicMock()):
            formats = CameraTest._get_supported_formats(
                mock_camera, "/dev/video0"
            )
        self.assertEqual(formats, expected_formats)

    @patch("fcntl.ioctl")
    def test_get_supported_formats_unexpected_error(self, mock_ioctl):
        mock_camera = MagicMock()
        mock_camera._get_supported_pixel_formats.return_value = [
            {
                "pixelformat": "YUYV",
                "pixelformat_int": 1448695129,
                "description": "YUV 4:2:2",
            }
        ]
        expected_formats = [
            {
                "pixelformat": "YUYV",
                "pixelformat_int": 1448695129,
                "description": "YUV 4:2:2",
                "resolutions": [],
            }
        ]
        mock_ioctl.side_effect = IOError(errno.EIO, "Unexpected error")
        with patch("builtins.open", MagicMock()):
            formats = CameraTest._get_supported_formats(
                mock_camera, "/dev/video0"
            )
        self.assertEqual(formats, expected_formats)

    @patch("fcntl.ioctl")
    def test_get_supported_formats_no_formats(self, mock_ioctl):
        mock_camera = MagicMock()
        mock_camera._get_supported_pixel_formats.return_value = []
        mock_ioctl.side_effect = self.ioctl_enum_framesizes_side_effect

        expected_formats = [
            {
                "pixelformat": "YUYV",
                "description": "YUYV",
                "resolutions": [[640, 480]],
            }
        ]

        with patch("builtins.open", MagicMock()):
            formats = CameraTest._get_supported_formats(
                mock_camera, "/dev/video0"
            )
        self.assertEqual(formats, expected_formats)

    @patch("camera_test.glob")
    def test_device_options(self, mock_glob):
        # Setup mock for glob to simulate available devices
        mock_glob.return_value = ["/dev/video0", "/dev/video1"]

        # Test highest device
        argv = ["led", "--highest-device"]
        args = parse_arguments(argv)
        self.assertEqual(args.device, "/dev/video1")

        # Test lowest device
        argv = ["led", "--lowest-device"]
        args = parse_arguments(argv)
        self.assertEqual(args.device, "/dev/video0")

    def test_still_subparser(self):
        argv = [
            "still",
            "--device",
            "/dev/video2",
            "-f",
            "/tmp/test.jpg",
            "-q",
        ]
        args = parse_arguments(argv)
        self.assertEqual(args.device, "/dev/video2")
        self.assertEqual(args.filename, "/tmp/test.jpg")
        self.assertEqual(args.quiet, True)

    def test_debug_flag(self):
        argv = ["detect"]
        args = parse_arguments(argv)
        self.assertEqual(args.log_level, logging.INFO)

        argv = ["--debug", "detect"]
        args = parse_arguments(argv)
        self.assertEqual(args.log_level, logging.DEBUG)

    def test_default_device(self):
        argv = ["display"]
        args = parse_arguments(argv)
        self.assertEqual(args.device, "/dev/video0")

    def test_output_directory(self):
        argv = ["resolutions", "--output", "output_dir"]
        args = parse_arguments(argv)
        self.assertEqual(args.output, "output_dir")

    @patch("camera_test.CameraTest._supported_formats_to_string")
    @patch("camera_test.CameraTest._get_supported_formats")
    def test_detect_and_show_camera_info_with_single_planar_capture_capability(
        self,
        mock_get_supported_formats,
        mock_supported_formats_to_string,
    ):
        """Test camera device supports the single planar capture capability"""
        mock_get_supported_formats.return_value = [
            {
                "description": "fake",
                "pixelformat": "fake",
                "resolutions": [[123, 987]],
            }
        ]
        mock_supported_formats_to_string.return_value = "Resolutions: fake"

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

    @patch("camera_test.CameraTest._supported_formats_to_string")
    @patch("camera_test.CameraTest._get_supported_formats")
    def test_detect_and_show_camera_info_with_multi_planar_capture_capability(
        self,
        mock_get_supported_formats,
        mock_supported_formats_to_string,
    ):
        """Test camera device supports the multi planar capture capability"""
        mock_get_supported_formats.return_value = [
            {
                "description": "fake",
                "pixelformat": "fake",
                "resolutions": [[123, 987]],
            }
        ]
        mock_supported_formats_to_string.return_value = "Resolutions: fake"

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

    @patch("camera_test.CameraTest._supported_formats_to_string")
    @patch("camera_test.CameraTest._get_supported_formats")
    def test_detect_and_show_camera_info_without_capture_capability(
        self,
        mock_get_supported_formats,
        mock_supported_formats_to_string,
    ):
        """Test camera device doesn't support the capture capability"""
        mock_get_supported_formats.return_value = [
            {
                "description": "YUYV",
                "pixelformat": "YUYV",
                "resolutions": [[640, 480]],
            }
        ]
        mock_supported_formats_to_string.return_value = "Resolutions: fake"

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
