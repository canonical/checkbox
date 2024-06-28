"""This module provides test cases for the edid_cycle module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, call, Mock, MagicMock

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

import edid_cycle


class ZapperEdidCycleTests(unittest.TestCase):
    """This class provides test cases for the edid_cycle module."""

    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("time.sleep", new=Mock)
    @patch("builtins.open")
    def test_discover_video_output_device(self, mock_open):
        """
        Check if the function automatically discover the port
        under test hot-plugging the Zapper monitor.
        """
        edid_cycle.EDID_FILES = [Path("1920x1080.edid")]

        mock_monitor = Mock()
        mock_monitor.get_current_resolutions.side_effect = [
            {},
            {"HDMI-1": "1920x1080"},
        ]

        port = edid_cycle.discover_video_output_device(
            "zapper-ip", mock_monitor
        )
        self.assertEqual(port, "HDMI-1")

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    def test_discover_video_output_device_error(self, mock_open):
        """
        Check if the function raises an exception when
        if fails to discover the video port.
        """
        edid_cycle.EDID_FILES = [Path("1920x1080.edid")]

        mock_monitor = Mock()
        mock_monitor.get_current_resolutions.return_value = {
            "HDMI-1": "1920x1080"
        }

        with self.assertRaises(IOError):
            edid_cycle.discover_video_output_device("zapper-ip", mock_monitor)

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    def test_test_edid(self, mock_open):
        """
        Check the function set an EDID and assert the actual
        resolution matches the request.
        """

        mock_monitor = Mock()
        mock_monitor.get_current_resolutions.side_effect = [
            {
                "eDP-1": "1280x1024",
            },
            {
                "eDP-1": "1280x1024",
                "HDMI-1": "1280x1024",  # when connected it's in mirror mode
            },
            {
                "eDP-1": "1280x1024",
                "HDMI-1": "1920x1080",  # and then we set extended mode
            },
        ]

        edid_cycle.test_edid(
            "zapper-ip", mock_monitor, Path("1920x1080.edid"), "HDMI-1"
        )
        mock_open.assert_called_with("1920x1080.edid", "rb")
        mock_monitor.set_extended_mode.assert_called_once_with()

    @patch("time.sleep", new=Mock)
    @patch("edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    def test_test_edid_error(self, mock_open):
        """
        Check the function raise an exception when the assertion
        on resolution fails.
        """
        mock_monitor = Mock()
        mock_monitor.get_current_resolutions.side_effect = [
            {
                "eDP-1": "1280x1024",
            },
            {
                "eDP-1": "1280x1024",
                "HDMI-1": "1280x1024",
            },
            {
                "eDP-1": "1280x1024",
                "HDMI-1": "1280x1024",  # still not at requested resolution
            },
        ]

        with self.assertRaises(AssertionError):
            edid_cycle.test_edid(
                "zapper-ip", mock_monitor, Path("1920x1080.edid"), "HDMI-1"
            )

    @patch("edid_cycle.display_info", Mock())
    @patch("edid_cycle.discover_video_output_device")
    def test_main_no_device(self, mock_discover):
        """Test if main function exits when no device is detected."""
        args = ["zapper-ip"]
        mock_discover.side_effect = IOError

        with self.assertRaises(SystemExit):
            edid_cycle.main(args)

    @patch("edid_cycle.display_info")
    def test_main_no_device(self, mock_display_info):
        """Test if main function exits when no monitor config is available."""
        mock_display_info.get_monitor_config.side_effect = ValueError
        with self.assertRaises(SystemExit):
            edid_cycle.main([])

    @patch("edid_cycle.display_info")
    @patch("edid_cycle.zapper_monitor")
    @patch("edid_cycle.test_edid")
    @patch("edid_cycle.discover_video_output_device")
    def test_main(
        self, mock_discover, mock_test_edid, mock_monitor, mock_display_info
    ):
        """
        Test if main function run the EDID test for every available EDID file.
        """
        args = ["zapper-ip"]
        edid_cycle.EDID_FILES = [
            Path("file1"),
            Path("file2"),
            Path("file3"),
        ]
        monitor_config = mock_display_info.get_monitor_config.return_value

        self.assertFalse(edid_cycle.main(args))
        mock_test_edid.assert_has_calls(
            [
                call(
                    "zapper-ip",
                    monitor_config,
                    Path("file1"),
                    mock_discover.return_value,
                ),
                call(
                    "zapper-ip",
                    monitor_config,
                    Path("file2"),
                    mock_discover.return_value,
                ),
                call(
                    "zapper-ip",
                    monitor_config,
                    Path("file3"),
                    mock_discover.return_value,
                ),
            ]
        )

        mock_test_edid.side_effect = AssertionError("Mismatch")
        self.assertTrue(edid_cycle.main(args))

        mock_monitor.assert_called_with("zapper-ip")

    @patch("edid_cycle._clear_edid")
    def test_zapper_monitor(self, mock_clear):
        """
        Test whether this context manager unplugs the Zapper monitor
        at exit.
        """

        with edid_cycle.zapper_monitor("zapper-ip"):
            pass

        mock_clear.assert_called_with("zapper-ip")
