import unittest
from textwrap import dedent
from unittest.mock import patch

from checkbox_support.parsers.xrandr import MonitorConfigX11


class MonitorConfigX11Tests(unittest.TestCase):
    """This class provides test cases for the MonitorConfig X11 class."""

    @patch("subprocess.check_output")
    def test_get_connected_monitors(self, mock_check_output):
        """
        Test whether the function returns a list of connected
        monitors, even if inactive.
        """

        # In xrandr, the '*' is used for active monitors
        mock_check_output.return_value = dedent(
            """
        Screen 0: minimum 320 x 200,
        eDP connected primary 1920x1080+0+607
           1680x1050     60.03 +
           1920x1080     60.03*
        HDMI-A-0 connected 2560x1440+1920+0
           2560x1440     59.95+
           1920x1080     60.00    50.00    59.94
        DisplayPort-0 disconnected (normal left inverted right x axis y axis)
        DisplayPort-1 disconnected (normal left inverted right x axis y axis)
        """
        )

        x11_monitor = MonitorConfigX11()
        monitors = x11_monitor.get_connected_monitors()
        self.assertSetEqual(monitors, {"eDP", "HDMI-A-0"})

    @patch("subprocess.check_output")
    def test_get_current_resolution(self, mock_check_output):
        """
        Test whether the function returns a dictionary of
        monitor-id:resolution for any active monitors.
        """

        mock_check_output.return_value = dedent(
            """
        Screen 0: minimum 320 x 200,
        eDP connected primary 1920x1080+0+607
           1680x1050     60.03 +
           1920x1080     60.03*
        HDMI-A-0 connected 2560x1440+1920+0
           2560x1440     59.95*+
           1920x1080     60.00    50.00    59.94
        DisplayPort-0 disconnected (normal left inverted right x axis y axis)
        DisplayPort-1 disconnected (normal left inverted right x axis y axis)
        """
        )

        x11_monitor = MonitorConfigX11()
        resolutions = x11_monitor.get_current_resolutions()
        self.assertEqual(
            resolutions, {"eDP": "1920x1080", "HDMI-A-0": "2560x1440"}
        )

    @patch("subprocess.run")
    @patch("subprocess.check_output")
    def test_set_extended_mode(self, mock_check_output, mock_run):
        """
        Test whether the function set the logical display
        configuration to two screens at preferred resolution
        placed horizontally.
        """
        mock_check_output.return_value = dedent(
            """
        Screen 0: minimum 320 x 200,
        eDP connected primary 1920x1080+0+607
           1680x1050     60.03 
           1920x1080     60.03*+
           2560x1440     59.95
        HDMI-A-0 connected 2560x1440+1920+0
           2560x1440     59.95*
           1920x1080     60.00    50.00    59.94
        DisplayPort-0 disconnected (normal left inverted right x axis y axis)
        DisplayPort-1 disconnected (normal left inverted right x axis y axis)
        """
        )

        x11_monitor = MonitorConfigX11()
        configuration = x11_monitor.set_extended_mode()
        expected = (
            "xrandr "
            "--output HDMI-A-0 --mode 2560x1440 --primary --pos 0x0 "
            "--output eDP --mode 1920x1080 --right-of HDMI-A-0"
        )
        mock_run.assert_called_with(expected.split(" "))
        expected = {
            "HDMI-A-0": "2560x1440",
            "eDP": "1920x1080",
        }
        self.assertDictEqual(configuration, expected)
