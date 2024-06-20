import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

from checkbox_support.helpers import display_info


class DisplayInfoTests(unittest.TestCase):
    """Test cases for the display_info module."""

    @patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"})
    @patch("checkbox_support.helpers.display_info.MonitorConfigGnome")
    def test_get_monitor_conf_gnome(self, mock_monitor):
        """
        Assert the function returns the Gnome DBus monitor config
        if the current desktop is Gnome.
        """
        monitor_config = display_info.get_monitor_config()
        self.assertEqual(mock_monitor.return_value, monitor_config)

    @patch.dict(
        os.environ,
        {"XDG_CURRENT_DESKTOP": "ubuntu:KDE", "XDG_SESSION_TYPE": "x11"},
    )
    @patch("checkbox_support.helpers.display_info.MonitorConfigX11")
    def test_get_monitor_conf_x11(self, mock_monitor):
        """
        Assert the function returns the x11 monitor config
        if the current desktop is not Gnome and session is X11.
        """
        monitor_config = display_info.get_monitor_config()
        self.assertEqual(mock_monitor.return_value, monitor_config)

    @patch.dict(
        os.environ,
        {"XDG_CURRENT_DESKTOP": "ubuntu:KDE", "XDG_SESSION_TYPE": "wayland"},
    )
    def test_get_monitor_conf_raises(self):
        """
        Assert the function raises an exception if the current host
        is not supported.
        """
        with self.assertRaises(ValueError):
            display_info.get_monitor_config()
