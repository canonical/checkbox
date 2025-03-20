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

import errno
import logging
import textwrap
import sys

import unittest
from unittest.mock import patch, MagicMock, call, mock_open
from tempfile import NamedTemporaryFile
import unittest.mock

from camera_test import (
    CameraTest,
    v4l2_capability,
    V4L2_FRMSIZE_TYPE_DISCRETE,
    V4L2_FRMSIZE_TYPE_STEPWISE,
    parse_arguments,
)


class CameraTestTests(unittest.TestCase):
    """This class provides test cases for the CameraTest class."""

    def test_init(self):
        mock_camera = CameraTest(
            device="/dev/video1",
            headless=True,
            output="/tmp",
            log_level=logging.DEBUG,
        )
        self.assertEqual(mock_camera.device, "/dev/video1")
        self.assertEqual(mock_camera.headless, True)
        self.assertEqual(mock_camera.output, "/tmp")
        self.assertEqual(mock_camera.log_level, logging.DEBUG)

    def test_init_gstreamer(self):
        mock_camera = MagicMock()
        mock_gi = MagicMock()
        with patch.dict(
            sys.modules, {"gi": mock_gi, "gi.repository": mock_gi.repository}
        ):
            CameraTest.init_gstreamer(mock_camera)

        self.assertEqual(mock_gi.require_version.call_count, 2)
        self.assertEqual(mock_camera.Gst.init.call_count, 1)

    def test_init_gtk(self):
        mock_camera = MagicMock()
        mock_gi = MagicMock()
        with patch.dict(
            sys.modules, {"gi": mock_gi, "gi.repository": mock_gi.repository}
        ):
            CameraTest.init_gtk(mock_camera)
        self.assertEqual(mock_gi.require_version.call_count, 1)
        self.assertEqual(mock_camera.Gtk.init.call_count, 1)

    @patch("camera_test.v4l2_capability", MagicMock())
    @patch("fcntl.ioctl", MagicMock())
    def test_detect(self):
        mock_camera = MagicMock()
        mock_camera._detect_and_show_camera_info.return_value = 0

        with patch("builtins.open", MagicMock()):
            result = CameraTest.detect(mock_camera)
        self.assertEqual(result, 0)

    def test_detect_and_show_camera_info_with_single_planar_capture_capability(
        self,
    ):
        """Test camera device supports the single planar capture capability"""
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = [
            {
                "description": "fake",
                "pixelformat": "fake",
                "resolutions": [[123, 987]],
            }
        ]
        mock_camera._get_supported_formats_to_string.return_value = (
            "Resolutions: fake"
        )

        fake_device = "/dev/video0"
        fake_v4l2_capability = v4l2_capability()
        fake_v4l2_capability.card = b"fake card"
        fake_v4l2_capability.driver = b"fake driver"
        fake_v4l2_capability.version = 123
        fake_v4l2_capability.capabilities = 0x1
        result = CameraTest._detect_and_show_camera_info(
            mock_camera, fake_device, fake_v4l2_capability
        )
        self.assertEqual(0, result)

    def test_detect_and_show_camera_info_with_multi_planar_capture_capability(
        self,
    ):
        """Test camera device supports the multi planar capture capability"""
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = [
            {
                "description": "fake",
                "pixelformat": "fake",
                "resolutions": [[123, 987]],
            }
        ]
        mock_camera._get_supported_formats_to_string.return_value = (
            "Resolutions: fake"
        )

        fake_device = "/dev/video0"
        fake_v4l2_capability = v4l2_capability()
        fake_v4l2_capability.card = b"fake card"
        fake_v4l2_capability.driver = b"fake driver"
        fake_v4l2_capability.version = 123
        fake_v4l2_capability.capabilities = 0x00001000
        result = CameraTest._detect_and_show_camera_info(
            mock_camera, fake_device, fake_v4l2_capability
        )
        self.assertEqual(0, result)

    def test_detect_and_show_camera_info_without_capture_capability(self):
        """Test camera device doesn't support the capture capability"""
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = [
            {
                "description": "YUYV",
                "pixelformat": "YUYV",
                "resolutions": [[640, 480]],
            }
        ]
        mock_camera._get_supported_formats_to_string.return_value = (
            "Resolutions: 640x480"
        )

        fake_device = "/dev/video0"
        fake_v4l2_capability = v4l2_capability()
        fake_v4l2_capability.card = b"fake card"
        fake_v4l2_capability.driver = b"fake driver"
        fake_v4l2_capability.version = 123
        fake_v4l2_capability.capabilities = 0x000010000
        result = CameraTest._detect_and_show_camera_info(
            mock_camera, fake_device, fake_v4l2_capability
        )
        self.assertEqual(1, result)

    def test_on_gst_message_eos(self):
        mock_camera = MagicMock()
        mock_camera.Gst.MessageType.EOS = 2
        mock_message = MagicMock()
        mock_message.type = 2
        mock_message.src.get_name.return_value = "pipeline"

        CameraTest._on_gst_message(mock_camera, None, mock_message)
        self.assertEqual(mock_camera.pipeline.set_state.call_count, 1)
        self.assertEqual(mock_camera.main_loop.quit.call_count, 1)

        # Test also debug mode
        mock_camera.log_level = logging.DEBUG
        with patch("logging.debug") as mocked_log:
            CameraTest._on_gst_message(mock_camera, None, mock_message)
            mocked_log.assert_called_once_with("End-of-stream")

    def test_on_gst_message_error(self):
        mock_camera = MagicMock()
        mock_camera.Gst.MessageType.ERROR = 3
        mock_message = MagicMock()
        mock_message.type = 3
        mock_error = MagicMock()
        mock_error.message.return_value = "error"
        mock_message.parse_error.return_value = (mock_error, "debug")

        with self.assertRaises(SystemExit):
            CameraTest._on_gst_message(mock_camera, None, mock_message)

        self.assertEqual(mock_camera.pipeline.set_state.call_count, 1)
        self.assertEqual(mock_camera.main_loop.quit.call_count, 1)

        # Test also debug mode
        mock_camera.log_level = logging.DEBUG
        with patch("logging.debug") as mocked_log:
            with self.assertRaises(SystemExit):
                CameraTest._on_gst_message(mock_camera, None, mock_message)
            mocked_log.assert_called_with("Debug info: debug")

    def test_on_gst_message_state_changed(self):
        mock_camera = MagicMock()
        mock_camera.Gst.MessageType.STATE_CHANGED = 4
        mock_message = MagicMock()
        mock_message.type = 4
        mock_message.src.get_name.return_value = "pipeline"
        mock_camera.log_level = logging.DEBUG

        old_state = MagicMock()
        old_state.value_nick = "old"
        new_state = MagicMock()
        new_state.value_nick = "new"
        mock_message.parse_state_changed.return_value = (
            old_state,
            new_state,
            None,
        )

        with patch("logging.debug") as mocked_log:
            CameraTest._on_gst_message(mock_camera, None, mock_message)
            mocked_log.assert_called_with(
                "Pipeline changed state from old to new"
            )

    def test_stop_pipeline(self):
        mock_camera = MagicMock()
        CameraTest._stop_pipeline(mock_camera)
        self.assertEqual(mock_camera.main_loop.quit.call_count, 1)
        self.assertEqual(mock_camera.pipeline.set_state.call_count, 1)

    def test_on_timeout(self):
        mock_camera = MagicMock()
        mock_camera.timeout = {}
        CameraTest._on_timeout(mock_camera)
        self.assertEqual(mock_camera._stop_pipeline.call_count, 1)
        self.assertEqual(mock_camera.timeout["global_timeout"], None)

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
        expected_str = textwrap.dedent(
            """
            Format: YUYV (YUYV)
            Resolutions: 640x480,320x240
            Format: fake (fake)
            Resolutions: 640x480
            """
        ).lstrip()

        mock_camera = MagicMock()
        return_str = CameraTest._supported_formats_to_string(
            mock_camera, formats
        )
        self.assertEqual(return_str, expected_str)

    def test_led(self):
        mock_camera = MagicMock()
        CameraTest.led(mock_camera)
        self.assertEqual(mock_camera.GLib.timeout_add_seconds.call_count, 1)
        self.assertEqual(mock_camera._setup_video_gstreamer.call_count, 1)

    def test_video(self):
        mock_camera = MagicMock()
        mock_camera.headless = False
        CameraTest.video(mock_camera)
        self.assertEqual(mock_camera.GLib.timeout_add_seconds.call_count, 1)
        self.assertEqual(mock_camera._setup_video_gstreamer.call_count, 1)

    def test_video_headless(self):
        mock_camera = MagicMock()
        mock_camera.headless = True
        CameraTest.video(mock_camera)
        self.assertEqual(mock_camera.GLib.timeout_add_seconds.call_count, 1)
        self.assertEqual(mock_camera._setup_video_gstreamer.call_count, 1)

    def test_setup_video_gstreamer(self):
        mock_camera = MagicMock()
        mock_make = mock_camera.Gst.ElementFactory.make
        mock_camera.Gst.State.PAUSED = "paused"
        mock_camera.Gst.State.PLAYING = "playing"

        CameraTest._setup_video_gstreamer(mock_camera)
        make_calls = mock_make.call_args_list
        self.assertEqual(
            make_calls,
            [
                call("v4l2src"),
                call("wrappercamerabinsrc"),
                call("camerabin", "pipeline"),
            ],
        )
        mock_camera.pipeline.set_state.assert_has_calls(
            [call("paused"), call("playing")]
        )
        mock_camera.main_loop.run.assert_called_with()

    def test_setup_video_gstreamer_with_sink(self):
        mock_camera = MagicMock()
        mock_make = mock_camera.Gst.ElementFactory.make
        mock_camera.Gst.State.PAUSED = "paused"
        mock_camera.Gst.State.PLAYING = "playing"

        CameraTest._setup_video_gstreamer(mock_camera, "sink")
        make_calls = mock_make.call_args_list
        self.assertEqual(
            make_calls,
            [
                call("v4l2src"),
                call("wrappercamerabinsrc"),
                call("camerabin", "pipeline"),
                call("sink"),
            ],
        )
        mock_camera.pipeline.set_state.assert_has_calls(
            [call("paused"), call("playing")]
        )
        mock_camera.main_loop.run.assert_called_with()

    def test_setup_video_gstreamer_no_supported_resolutions(self):
        mock_camera = MagicMock()
        mock_make = mock_camera.Gst.ElementFactory.make
        mock_caps = MagicMock()
        mock_caps.get_size.return_value = 0
        mock_make.return_value.get_property.return_value = mock_caps

        with self.assertRaises(SystemExit):
            CameraTest._setup_video_gstreamer(mock_camera)

    def test_setup_video_gstreamer_error(self):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_camera.GLib.Error = Exception
        mock_camera.GLib.MainLoop.return_value.run.side_effect = Exception()
        mock_camera.Gst.State.NULL = "null"
        CameraTest._setup_video_gstreamer(mock_camera)

        self.assertEqual(mock_camera.main_loop.run.call_count, 1)
        mock_camera.pipeline.set_state.assert_called_with("null")

    def test_image(self):
        mock_camera = MagicMock()
        mock_camera.output = "/tmp/test.jpg"
        mock_camera._get_default_format.return_value = {
            "pixelformat": "YUYV",
            "description": "YUYV",
            "resolutions": [[640, 480], [320, 240]],
        }

        CameraTest.image(mock_camera)
        self.assertEqual(mock_camera._capture_image.call_count, 1)

    def test_image_without_output(self):
        mock_camera = MagicMock()
        mock_camera.output = None
        mock_camera._get_default_format.return_value = {
            "pixelformat": "YUYV",
            "description": "YUYV",
            "resolutions": [[640, 480], [320, 240]],
        }

        with patch("tempfile.NamedTemporaryFile"):
            CameraTest.image(mock_camera)
            self.assertEqual(mock_camera._capture_image.call_count, 1)

    def test_capture_image_helper(self):
        mock_camera = MagicMock()
        mock_camera._capture_image_fswebcam.return_value = True
        mock_camera._display_image.return_value = True
        mock_camera.headless = False
        CameraTest._capture_image(
            mock_camera, "/tmp/test.jpg", 640, 480, "YUYV"
        )
        self.assertEqual(mock_camera._capture_image_fswebcam.call_count, 1)
        self.assertEqual(mock_camera._display_image.call_count, 1)

    def test_capture_image_headless(self):
        mock_camera = MagicMock()
        mock_camera._capture_image_fswebcam.return_value = True
        mock_camera.headless = True
        CameraTest._capture_image(
            mock_camera, "/tmp/test.jpg", 640, 480, "YUYV"
        )
        self.assertEqual(mock_camera._display_image.call_count, 0)

    def test_capture_image_helper_fswebcam_fails(self):
        mock_camera = MagicMock()
        mock_camera._capture_image_fswebcam.return_value = False
        CameraTest._capture_image(
            mock_camera, "/tmp/test.jpg", 640, 480, "YUYV"
        )
        self.assertEqual(mock_camera._capture_image_gstreamer.call_count, 1)

    @patch("camera_test.check_call")
    @patch("os.path.getsize")
    def test_capture_image_fswebcam(
        self, mock_get_size: MagicMock, mock_check_call: MagicMock
    ):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_get_size.return_value = 1
        result = CameraTest._capture_image_fswebcam(
            mock_camera, "/tmp/test.jpg", 640, 480, "MJPG"
        )
        self.assertEqual(mock_check_call.call_count, 1)
        self.assertEqual(result, True)

        mock_check_call.reset_mock()
        mock_camera.photo_wait_seconds = 0
        result = CameraTest._capture_image_fswebcam(
            mock_camera, "/tmp/test.jpg", 640, 480, "MJPG"
        )
        # delay arg should not be inserted when wait is 0
        self.assertFalse(
            any("-D" in arg for arg in mock_check_call.call_args[-1])
        )

        mock_check_call.reset_mock()
        mock_camera.photo_wait_seconds = 0
        result = CameraTest._capture_image_fswebcam(
            mock_camera, "/tmp/test.jpg", 640, 480, None
        )
        # pixel format arg should not be inserted if not specified
        self.assertFalse(
            any("-p" in arg for arg in mock_check_call.call_args[-1])
        )

    @patch("camera_test.check_call", MagicMock())
    @patch("os.path.getsize")
    def test_capture_image_fswebcam_empty(self, mock_get_size):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_get_size.return_value = 0
        result = CameraTest._capture_image_fswebcam(
            mock_camera, "/tmp/test.jpg", 640, 480, "YUYV"
        )
        self.assertEqual(result, False)

    @patch("camera_test.check_call")
    def test_capture_image_fswebcam_error(self, mock_check_call):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_check_call.return_value = OSError()
        result = CameraTest._capture_image_fswebcam(
            mock_camera, "/tmp/test.jpg", 640, 480, "YUYV"
        )
        self.assertEqual(result, False)

    def test_capture_image_gstreamer(self):
        with self.assertRaises(ValueError):
            CameraTest(wait_seconds=-1)

        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_make = mock_camera.Gst.ElementFactory.make
        mock_camera.Gst.State.PLAYING = "playing"

        CameraTest._capture_image_gstreamer(
            mock_camera, "/tmp/test.jpg", 640, 480, "YUYV"
        )
        make_calls = mock_make.call_args_list
        print(make_calls, flush=True)
        self.assertListEqual(
            make_calls,
            [
                call("v4l2src", "video-source"),
                call("capsfilter", "caps"),
                call("valve", "photo-valve"),
                call("multifilesink", "sink"),  # this gets created earlier
                call("jpegenc", "encoder"),
            ],
        )
        mock_camera.pipeline.set_state.assert_has_calls([call("playing")])
        mock_camera.main_loop.run.assert_called_with()

    def test_capture_image_gstreamer_no_delay(self):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 0
        mock_valve = MagicMock()

        mock_camera.Gst.ElementFactory.make.side_effect = lambda *args: (
            mock_valve if "valve" in args else unittest.mock.DEFAULT
        )

        CameraTest._capture_image_gstreamer(
            mock_camera, "/tmp/test.jpg", 640, 480, "YUYV"
        )
        mock_valve.set_property.assert_called_with("drop", False)

    def test_capture_image_gstreamer_bayer(self):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_make = mock_camera.Gst.ElementFactory.make

        CameraTest._capture_image_gstreamer(
            mock_camera, "/tmp/test.jpg", 640, 480, "RG10"
        )
        make_calls = mock_make.call_args_list
        print(make_calls, flush=True)
        self.assertEqual(
            make_calls,
            [
                call("v4l2src", "video-source"),
                call("capsfilter", "caps"),
                call("bayer2rgb", "bayer2rgb"),
                call("valve", "photo-valve"),
                call("multifilesink", "sink"),
                call("jpegenc", "encoder"),
            ],
        )

    def test_capture_image_gstreamer_jpeg(self):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_camera.timeout = {}
        mock_GLib_timout_add = mock_camera.GLib.timeout_add_seconds

        CameraTest._capture_image_gstreamer(
            mock_camera, "/tmp/test.jpg", 640, 480, "MJPG"
        )
        make_calls = mock_camera.Gst.ElementFactory.make.call_args_list
        print(make_calls, flush=True)
        self.assertListEqual(
            make_calls,
            [
                call("v4l2src", "video-source"),
                call("capsfilter", "caps"),
                call("valve", "photo-valve"),
                call("multifilesink", "sink"),
            ],
        )
        self.assertTrue(mock_GLib_timout_add.called)
        # now simulate the timeout
        self.assertEqual(mock_GLib_timout_add.call_count, 3)
        for mock_timeout_call in mock_GLib_timout_add.call_args_list:
            # 0 extracts the (timeout_seconds, handler) tuple
            # 1 grabs the handler, then call it
            mock_timeout_call[0][1]()

        self.assertIsNone(mock_camera.timeout["eos_timeout"])
        self.assertIsNone(mock_camera.timeout["open_valve"])

    def test_capture_image_gstreamer_error(self):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_camera.GLib.Error = Exception
        mock_camera.GLib.MainLoop.return_value.run.side_effect = Exception()
        mock_camera.Gst.State.NULL = "null"
        CameraTest._capture_image_gstreamer(
            mock_camera, "/tmp/test.jpg", 640, 480, "RG10"
        )

        self.assertEqual(mock_camera.main_loop.run.call_count, 1)
        mock_camera.pipeline.set_state.assert_called_with("null")

    def test_capture_image_gstreamer_remove_timeout(self):
        mock_camera = MagicMock()
        mock_camera.photo_wait_seconds = 3
        mock_camera.timeout = {}
        mock_camera.GLib.timeout_add_seconds.return_value = "timeout"
        CameraTest._capture_image_gstreamer(
            mock_camera, "/tmp/test.jpg", 640, 480, "RG10"
        )

        mock_camera.GLib.source_remove.assert_called_with("timeout")

    def test_display_image(self):
        mock_camera = MagicMock()
        CameraTest._display_image(mock_camera, "/tmp/test.jpg", 640, 480)
        mock_camera.Gtk.Window.assert_called_with(title="Image Viewer")
        mock_camera.Gtk.Image.new_from_file.assert_called_with("/tmp/test.jpg")
        mock_camera.GLib.timeout_add_seconds.assert_called_with(
            10, mock_camera.Gtk.main_quit
        )
        mock_camera.Gtk.main.assert_called_with()

    @patch("tempfile.NamedTemporaryFile", MagicMock())
    def test_resolutions(self):
        # Get a magic mock object for the camera with the same methods
        mock_camera = MagicMock()
        mock_camera._get_default_format.return_value = {
            "pixelformat": "YUYV",
            "description": "YUYV",
            "resolutions": [[640, 480], [320, 240]],
        }
        mock_camera._validate_image.return_value = True

        self.assertEqual(CameraTest.resolutions(mock_camera), 0)

        self.assertEqual(mock_camera._get_default_format.call_count, 1)
        self.assertEqual(mock_camera._save_debug_image.call_count, 1)
        self.assertEqual(mock_camera._capture_image.call_count, 2)
        self.assertEqual(mock_camera._validate_image.call_count, 2)

        # Test that the function also works with no output
        mock_camera.args["output"] = None
        self.assertEqual(CameraTest.resolutions(mock_camera), 0)

    @patch("tempfile.NamedTemporaryFile", MagicMock())
    def test_resolutions_wrong_validation(self):
        mock_camera = MagicMock()
        mock_camera._get_default_format.return_value = {
            "pixelformat": "YUYV",
            "description": "YUYV",
            "resolutions": [[640, 480], [320, 240]],
        }
        mock_camera._validate_image.return_value = False

        self.assertEqual(CameraTest.resolutions(mock_camera), 1)

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
        self.assertEqual(mock_camera._capture_image.call_count, 1)

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

    def test_get_default_format(self):
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = [
            {
                "pixelformat": "YUYV",
                "description": "YUYV",
                "resolutions": [[640, 480], [320, 240]],
            }
        ]
        mock_camera._validate_image.return_value = True

        format = CameraTest._get_default_format(mock_camera)
        self.assertEqual(format["pixelformat"], "YUYV")

    def test_get_default_format_no_formats(self):
        mock_camera = MagicMock()
        mock_camera._get_supported_formats.return_value = []
        with self.assertRaises(SystemExit):
            CameraTest._get_default_format(mock_camera)

    def test_get_default_format_broken_format(self):
        mock_camera = MagicMock()

        mock_camera._get_supported_formats.return_value = [
            {
                "pixelformat": "YUYV",
                "description": "YUYV",
                "resolutions": [],
            }
        ]
        with self.assertRaises(ValueError):
            CameraTest._get_default_format(mock_camera)

    @patch("os.path.exists")
    def test_validate_image_no_file(self, mock_exists):
        mock_camera = MagicMock()
        mock_exists.return_value = False
        result = CameraTest._validate_image(
            mock_camera, "/tmp/test.jpg", 480, 320
        )
        self.assertEqual(result, False)

    @patch("os.path.exists")
    def test_validate_image_wrong_format(self, mock_exists):
        mock_camera = MagicMock()
        mock_exists.return_value = True
        with patch("builtins.open", mock_open(read_data=b"")):
            with patch("builtins.print") as mocked_print, patch(
                "camera_test.check_output"
            ) as mock_check_output:
                mock_check_output.return_value = "inode/empty"
                result = CameraTest._validate_image(
                    mock_camera, "/tmp/test.jpg", 480, 320
                )
                # should not even start reading the file if the `file` command
                # check didn't pass
                mocked_print.assert_any_call(
                    "Image is not a standard JPEG file"
                )
                self.assertEqual(result, False)

    @patch("builtins.open")
    @patch("os.path.exists")
    @patch("camera_test.check_output")
    def test_validate_image_correct_jpeg_format(
        self, mock_output, mock_exists, mock_open
    ):
        mock_camera = MagicMock()
        mock_exists.return_value = True

        # Create a temporary file with a valid 1x1 JPEG image
        # ffc0 is the start of the dimension section
        # ffc0 00 11 08 00 01 00 01
        #               h^^^^ w^^^^
        data = (
            "ffd8ffe000104a46494600010101004800480000fffe001343726561746564207"
            "76974682047494d50ffdb00430001010101010101010101010101010101010101"
            "01010101010101010101010101010101010101010101010101010101010101010"
            "1010101010101010101010101ffdb004301010101010101010101010101010101"
            "01010101010101010101010101010101010101010101010101010101010101010"
            "101010101010101010101010101010101ffc00011080001000103011100021101"
            "031101ffc4001400010000000000000000000000000000000bffc400141001000"
            "00000000000000000000000000000ffc400140101000000000000000000000000"
            "00000000ffc40014110100000000000000000000000000000000ffda000c03010"
            "002110311003f003ff07fffd90000"  # shouldn't fail with trailing 0s
        )

        with NamedTemporaryFile() as f:
            f.write(bytes.fromhex(data))
            f.seek(0)
            mock_open.return_value = f
            mock_output.return_value = "image/jpeg"
            result = CameraTest._validate_image(mock_camera, f.name, 1, 1)
            self.assertEqual(result, True)

    @patch("camera_test.glob")
    def test_device_options(self, mock_glob):
        # Setup mock for glob to simulate available devices
        mock_glob.return_value = ["/dev/video0", "/dev/video1"]

        # Test highest device
        argv = ["led", "--highest-device"]
        args = parse_arguments(argv)
        self.assertEqual(args["device"], "/dev/video1")

        # Test lowest device
        argv = ["led", "--lowest-device"]
        args = parse_arguments(argv)
        self.assertEqual(args["device"], "/dev/video0")

    def test_image_subparser(self):
        argv = [
            "image",
            "--device",
            "/dev/video2",
            "-o",
            "/tmp/test.jpg",
            "-hl",
        ]
        args = parse_arguments(argv)
        self.assertEqual(args["device"], "/dev/video2")
        self.assertEqual(args["output"], "/tmp/test.jpg")
        self.assertEqual(args["headless"], True)

    def test_debug_flag(self):
        argv = ["detect"]
        args = parse_arguments(argv)
        self.assertEqual(args["log_level"], logging.INFO)

        argv = ["--debug", "detect"]
        args = parse_arguments(argv)
        self.assertEqual(args["log_level"], logging.DEBUG)

    def test_default_device(self):
        argv = ["video"]
        args = parse_arguments(argv)
        self.assertEqual(args["device"], "/dev/video0")

    def test_output_directory(self):
        argv = ["resolutions", "--output", "output_dir"]
        args = parse_arguments(argv)
        self.assertEqual(args["output"], "output_dir")

    def tearDown(self):
        # release stdout
        sys.stdout = sys.__stdout__


if __name__ == "__main__":
    unittest.main()
