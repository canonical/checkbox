"""This module provides test cases for the edid_cycle module."""
import unittest
from unittest.mock import patch, call, Mock

from bin import edid_cycle


class ZapperEdidCycleTests(unittest.TestCase):
    """This class provides test cases for the edid_cycle module."""

    @patch("time.sleep", new=Mock)
    @patch("bin.edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_discover_video_output_device(
        self, mock_check, mock_getenv, mock_open
    ):
        """
        Check if the function automatically discover the port
        under test with output given by randr in different conditions.
        """
        disconnected_output = {"x11": "Monitors: 0", "wayland": ""}

        connected_output = {
            "x11": (
                "Monitors: 1\n"
                " 0: +HDMI-1 1920/576x1080/324+800+1080 HDMI-1\n"
            ),
            "wayland": (
                "x: 0, y: 0, scale: 1, rotation: normal, primary: yes\n"
                "associated physical monitors:\n"
                "    HDMI-1 TSB PI-KVM Video 0x88888800\n\n"
                "HDMI-1 TSB PI-KVM Video\n"
            ),
        }

        edid_cycle.EDID_FILES = ["1920x1080.edid"]

        for env in ["x11", "wayland"]:
            mock_getenv.return_value = env
            mock_open.reset_mock()

            # Happy Case
            mock_check.side_effect = [
                disconnected_output[env],
                connected_output[env],
            ]

            port = edid_cycle.discover_video_output_device("zapper-ip")
            assert port == "HDMI-1"

            # Failure
            mock_check.side_effect = None
            mock_check.return_value = connected_output[env]
            with self.assertRaises(IOError):
                edid_cycle.discover_video_output_device("zapper-ip")

    @patch("time.sleep", new=Mock)
    @patch("bin.edid_cycle.zapper_run", new=Mock)
    @patch("builtins.open")
    @patch("os.getenv")
    @patch("subprocess.check_output")
    def test_test_edid(self, mock_check, mock_getenv, mock_open):
        """
        Check the function set an EDID and assert the actual
        resolution matches the request.
        """

        disconnected_output = {"x11": "Monitors: 0", "wayland": ""}

        connected_output = {
            "x11": "Monitors: 1\n 0: +HDMI-1 1920/576x1080/324+800+1080",
            "wayland": (
                "x: 0, y: 0, scale: 1, rotation: normal, primary: yes\n"
                "associated physical monitors:\n"
                "    HDMI-1 TSB PI-KVM Video 0x88888800"
            ),
        }

        resolution_output = {
            "x11": (
                "Screen 0: minimum 320 x 200\n"
                "HDMI-1 connected 1920x1080+800+1080\n"
                "   1920x1080     49.88*+"
            ),
            "wayland": (
                "HDMI-1 TSB PI-KVM Video 0x88888800\n"
                "    1920x1080@49.939697265625  1920x1080  49.94*+ "
            ),
        }

        for env in ["x11", "wayland"]:
            mock_getenv.return_value = env
            mock_open.reset_mock()

            # Happy case
            mock_check.side_effect = [
                disconnected_output[env],
                connected_output[env],
                resolution_output[env],
            ]

            edid_cycle.test_edid("zapper-ip", "1920x1080.edid", "HDMI-1")
            mock_open.assert_called_with("1920x1080.edid", "rb")

            # Times out when switching
            mock_check.side_effect = None
            mock_check.return_value = disconnected_output[env]

            with self.assertRaises(AssertionError):
                edid_cycle.test_edid("zapper-ip", "1920x1080.edid", "HDMI-1")

            # No output
            mock_check.return_value = None
            mock_check.side_effect = [
                disconnected_output[env],
                connected_output[env],
                "",
            ]

            with self.assertRaises(AssertionError):
                edid_cycle.test_edid("zapper-ip", "1280x800.edid", "HDMI-1")

            # Wrong resolution
            mock_check.return_value = None
            mock_check.side_effect = [
                disconnected_output[env],
                connected_output[env],
                resolution_output[env],
            ]

            with self.assertRaises(AssertionError):
                edid_cycle.test_edid("zapper-ip", "1280x800.edid", "HDMI-1")

    @patch("bin.edid_cycle.discover_video_output_device")
    def test_main_no_device(self, mock_discover):
        """Test if main function exits when no device is detected."""
        args = ["zapper-ip"]
        mock_discover.side_effect = IOError

        with self.assertRaises(SystemExit):
            edid_cycle.main(args)

    @patch("bin.edid_cycle.test_edid")
    @patch("bin.edid_cycle.discover_video_output_device")
    def test_main(self, mock_discover, mock_test_edid):
        """
        Test if main function run the EDID test for every available EDID file.
        """
        args = ["zapper-ip"]
        edid_cycle.EDID_FILES = ["file1", "file2", "file3"]

        assert not edid_cycle.main(args)
        mock_test_edid.assert_has_calls(
            [
                call("zapper-ip", "file1", mock_discover.return_value),
                call("zapper-ip", "file2", mock_discover.return_value),
                call("zapper-ip", "file3", mock_discover.return_value),
            ]
        )

        mock_test_edid.side_effect = AssertionError
        assert edid_cycle.main(args)
