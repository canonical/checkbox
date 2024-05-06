"""This module provides test cases for the edid_cycle module."""

import unittest
import textwrap
from pathlib import Path
from unittest.mock import patch, call, Mock

import edid_cycle

from checkbox_support.helpers.display_info import Mode


class ZapperEdidCycleTests(unittest.TestCase):
    """This class provides test cases for the edid_cycle module."""

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_discover_video_output_device_x11(
        self, mock_check, mock_getenv, mock_open
    ):
        """
        Check if the function automatically discover the port
        under test with output given by randr on X11.
        """
        mock_getenv.return_value = "x11"
        edid_cycle.EDID_FILES = [Path("1920x1080.edid")]

        disconnected_output = "Monitors: 0"
        connected_output = textwrap.dedent(
            """
            HDMI-1-0 connected 1920x1080+1920+0 (normal) 576mm x 324mm
                1920x1080     49.88*+
            """
        )

        mock_check.side_effect = [
            disconnected_output,
            connected_output,
        ]

        port = edid_cycle.discover_video_output_device("zapper-ip")
        self.assertEqual(port, "HDMI-1-0")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_discover_video_output_device_x11_error(
        self, mock_check, mock_getenv, mock_open
    ):
        """
        Check if the function raises an exception when
        if fails to discover the video port on X11.
        """
        mock_getenv.return_value = "x11"
        edid_cycle.EDID_FILES = [Path("1920x1080.edid")]

        connected_output = textwrap.dedent(
            """
            Monitors: 1
             0: +HDMI-1 1920/576x1080/324+800+1080 HDMI-1
            """
        )

        mock_check.side_effect = None
        mock_check.return_value = connected_output
        with self.assertRaises(IOError):
            edid_cycle.discover_video_output_device("zapper-ip")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_discover_video_output_device_wayland(
        self, mock_check, mock_getenv, mock_open
    ):
        """
        Check if the function automatically discover the port
        under test with output given by randr on Wayland.
        """
        mock_getenv.return_value = "wayland"
        edid_cycle.EDID_FILES = [Path("1920x1080.edid")]

        disconnected_output = ""
        connected_output = textwrap.dedent(
            """
            x: 0, y: 0, scale: 1, rotation: normal, primary: yes
            associated physical monitors:
                HDMI-1 TSB PI-KVM Video 0x88888800

            HDMI-1 TSB PI-KVM Video
                3840x2160@120.000  3840x2160       120.00* [x1.00]
            """
        )

        mock_check.side_effect = [
            disconnected_output,
            connected_output,
        ]

        port = edid_cycle.discover_video_output_device("zapper-ip")
        self.assertEqual(port, "HDMI-1")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_discover_video_output_device_wayland_error(
        self, mock_check, mock_getenv, mock_open
    ):
        """
        Check if the function raises an exception when
        if fails to discover the video port on Wayland.
        """
        mock_getenv.return_value = "wayland"
        edid_cycle.EDID_FILES = [Path("1920x1080.edid")]

        connected_output = textwrap.dedent(
            """
            x: 0, y: 0, scale: 1, rotation: normal, primary: yes
            associated physical monitors:
                HDMI-1 TSB PI-KVM Video 0x88888800

            HDMI-1 TSB PI-KVM Video
            """
        )

        mock_check.side_effect = None
        mock_check.return_value = connected_output
        with self.assertRaises(IOError):
            edid_cycle.discover_video_output_device("zapper-ip")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_test_edid_x11(self, mock_check, mock_getenv, mock_open):
        """
        Check the function set an EDID and assert the actual
        resolution matches the request on X11.
        """
        mock_getenv.return_value = "x11"

        disconnected_output = "Monitors: 0"

        connected_output = textwrap.dedent(
            """
            Monitors: 1
             0: +HDMI-1 1920/576x1080/324+800+1080",
            """
        )

        resolution_output = textwrap.dedent(
            """
            Screen 0: minimum 320 x 200
            HDMI-1 connected 1920x1080+800+1080
               1920x1080     49.88*+"
            """
        )

        mock_check.side_effect = [
            disconnected_output,
            connected_output,
            resolution_output,
        ]

        edid_cycle.test_edid("zapper-ip", Path("1920x1080.edid"), "HDMI-1")
        mock_open.assert_called_with("1920x1080.edid", "rb")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_test_edid_x11_error(self, mock_check, mock_getenv, mock_open):
        """
        Check the function raise an exception when the assertion
        on resolution fails on X11.
        """
        mock_getenv.return_value = "x11"

        disconnected_output = "Monitors: 0"

        connected_output = textwrap.dedent(
            """
            Monitors: 1
             0: +HDMI-1 1920/576x1080/324+800+1080",
            """
        )

        resolution_output = textwrap.dedent(
            """
            Screen 0: minimum 320 x 200
            HDMI-1 connected 1920x1080+800+1080
               1920x1080     49.88*+"
            """
        )

        # Times out when switching
        mock_check.side_effect = None
        mock_check.return_value = disconnected_output

        with self.assertRaises(AssertionError):
            edid_cycle.test_edid("zapper-ip", Path("1920x1080.edid"), "HDMI-1")

        # No output
        mock_check.return_value = None
        mock_check.side_effect = [
            disconnected_output,
            connected_output,
            "",
        ]

        with self.assertRaises(AssertionError):
            edid_cycle.test_edid("zapper-ip", Path("1280x800.edid"), "HDMI-1")

        # Wrong resolution
        mock_check.return_value = None
        mock_check.side_effect = [
            disconnected_output,
            connected_output,
            resolution_output,
        ]

        with self.assertRaises(AssertionError):
            edid_cycle.test_edid("zapper-ip", Path("1280x800.edid"), "HDMI-1")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_test_edid_wayland(self, mock_check, mock_getenv, mock_open):
        """
        Check the function set an EDID and assert the actual
        resolution matches the request on Wayland.
        """
        mock_getenv.return_value = "wayland"

        disconnected_output = ""

        connected_output = textwrap.dedent(
            """
            x: 0, y: 0, scale: 1, rotation: normal, primary: yes
            associated physical monitors:
                HDMI-1 TSB PI-KVM Video 0x88888800
            """
        )

        resolution_output = textwrap.dedent(
            """
            HDMI-1 TSB PI-KVM Video 0x88888800
                1920x1080@49.939697265625  1920x1080  49.94*+
            """
        )

        mock_check.side_effect = [
            disconnected_output,
            connected_output,
            resolution_output,
        ]

        edid_cycle.test_edid("zapper-ip", Path("1920x1080.edid"), "HDMI-1")
        mock_open.assert_called_with("1920x1080.edid", "rb")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_test_edid_wayland_error(self, mock_check, mock_getenv, mock_open):
        """
        Check the function raise an exception when the assertion
        on resolution fails on Wayland.
        """
        mock_getenv.return_value = "wayland"

        disconnected_output = ""

        connected_output = textwrap.dedent(
            """
            x: 0, y: 0, scale: 1, rotation: normal, primary: yes
            associated physical monitors:
                HDMI-1 TSB PI-KVM Video 0x88888800
            """
        )

        resolution_output = textwrap.dedent(
            """
            HDMI-1 TSB PI-KVM Video 0x88888800
                1920x1080@49.939697265625  1920x1080  49.94*+
            """
        )

        # Times out when switching
        mock_check.side_effect = None
        mock_check.return_value = disconnected_output

        with self.assertRaises(AssertionError):
            edid_cycle.test_edid("zapper-ip", Path("1920x1080.edid"), "HDMI-1")

        # No output
        mock_check.return_value = None
        mock_check.side_effect = [
            disconnected_output,
            connected_output,
            "",
        ]

        with self.assertRaises(AssertionError):
            edid_cycle.test_edid("zapper-ip", Path("1280x800.edid"), "HDMI-1")

        # Wrong resolution
        mock_check.return_value = None
        mock_check.side_effect = [
            disconnected_output,
            connected_output,
            resolution_output,
        ]

        with self.assertRaises(AssertionError):
            edid_cycle.test_edid("zapper-ip", Path("1280x800.edid"), "HDMI-1")

    @patch("edid_cycle.discover_video_output_device")
    def test_main_no_device(self, mock_discover):
        """Test if main function exits when no device is detected."""
        args = ["zapper-ip"]
        mock_discover.side_effect = IOError

        with self.assertRaises(SystemExit):
            edid_cycle.main(args)

    @patch("edid_cycle.test_edid")
    @patch("edid_cycle.discover_video_output_device")
    def test_main(self, mock_discover, mock_test_edid):
        """
        Test if main function run the EDID test for every available EDID file.
        """
        args = ["zapper-ip"]
        edid_cycle.EDID_FILES = [
            Path("file1"),
            Path("file2"),
            Path("file3"),
        ]

        self.assertFalse(edid_cycle.main(args))
        mock_test_edid.assert_has_calls(
            [
                call("zapper-ip", Path("file1"), mock_discover.return_value),
                call("zapper-ip", Path("file2"), mock_discover.return_value),
                call("zapper-ip", Path("file3"), mock_discover.return_value),
            ]
        )

        mock_test_edid.side_effect = AssertionError("Mismatch")
        self.assertTrue(edid_cycle.main(args))


class GetActiveDevicesTests(unittest.TestCase):
    @patch("edid_cycle.get_display_modes")
    def test_get_active_devices_happy(self, mock_get_display_info):
        """
        Test if the function returns the active devices.
        """
        mock_get_display_info.return_value = {
            "HDMI-1": [],
            "HDMI-2": [Mode("1920x1080", 60.00, False, True)],
            # The next one has a preferred mode, but not active
            "HDMI-3": [Mode("1920x1080", 60.00, True, False)],
            "HDMI-4": [],
        }

        active_devices = edid_cycle.get_active_devices()
        self.assertEqual(active_devices, {"HDMI-2"})

    @patch("edid_cycle.get_display_modes")
    def test_get_active_devices_empty(self, mock_get_display_info):
        """
        Test if the function returns an empty set when no active devices.
        """
        mock_get_display_info.return_value = dict()
        active_devices = edid_cycle.get_active_devices()
        self.assertEqual(active_devices, set())
