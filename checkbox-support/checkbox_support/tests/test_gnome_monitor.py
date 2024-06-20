import sys
import unittest
from unittest.mock import patch, Mock, MagicMock

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

from gi.repository import GLib, Gio
from checkbox_support.dbus.gnome_monitor import MonitorConfigGnome


class MonitorConfigGnomeTests(unittest.TestCase):
    """This class provides test cases for the MonitorCOnfig DBus class."""

    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_get_current_resolution(self, mock_dbus_proxy):
        """
        Test whether the function returns a dictionary of
        monitor-id:resolution for any active monitors.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()
        mock_proxy.call_sync.return_value = (
            1,
            [
                (
                    ("eDP-1", "LGD", "0x06b3", "0x00000000"),
                    [
                        (
                            "1920x1200@59.950",
                            1920,
                            1200,
                            59.950172424316406,
                            1.0,
                            [1.0, 2.0],
                            {
                                "is-current": GLib.Variant("b", True),
                                "is-preferred": GLib.Variant("b", True),
                            },
                        )
                    ],
                    {
                        "is-builtin": GLib.Variant("b", True),
                        "display-name": GLib.Variant("s", "Built-in display"),
                    },
                ),
                (
                    ("HDMI-1", "LGD", "0x06b3", "0x00000000"),
                    [
                        (
                            "2560x1440@59.950",
                            2560,
                            1440,
                            59.950172424316406,
                            1.0,
                            [1.0, 2.0],
                            {
                                "is-current": GLib.Variant("b", True),
                                "is-preferred": GLib.Variant("b", True),
                            },
                        )
                    ],
                    {
                        "is-builtin": GLib.Variant("b", False),
                        "display-name": GLib.Variant("s", "External Display"),
                    },
                ),
            ],
            [],
            {},
        )
        resolutions = gnome_monitor.get_current_resolutions()
        self.assertEqual(
            resolutions, {"eDP-1": "1920x1200", "HDMI-1": "2560x1440"}
        )

    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_set_extended_mode(self, mock_dbus_proxy):
        """
        Test whether the function set the logical display
        configuration to two screens at maximum resolution
        placed horizontally.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()
        mock_proxy.call_sync.return_value = (
            1,
            [
                (
                    ("eDP-1", "LGD", "0x06b3", "0x00000000"),
                    [
                        (
                            "1920x1200@59.950",
                            1920,
                            1200,
                            59.950172424316406,
                            1.0,
                            [1.0, 2.0],
                            {
                                "is-current": GLib.Variant("b", True),
                                "is-preferred": GLib.Variant("b", True),
                            },
                        )
                    ],
                    {
                        "is-builtin": GLib.Variant("b", True),
                        "display-name": GLib.Variant("s", "Built-in display"),
                    },
                ),
                (
                    ("HDMI-1", "LGD", "0x06b3", "0x00000000"),
                    [
                        (
                            "2560x1440@59.950",
                            2560,
                            1440,
                            59.950172424316406,
                            1.0,
                            [1.0, 2.0],
                            {
                                "is-current": GLib.Variant("b", True),
                                "is-preferred": GLib.Variant("b", True),
                            },
                        )
                    ],
                    {
                        "is-builtin": GLib.Variant("b", False),
                        "display-name": GLib.Variant("s", "External Display"),
                    },
                ),
            ],
            [],
            {},
        )
        gnome_monitor.set_extended_mode()

        logical_monitors = [
            (0, 0, 1.0, 0, True, [("eDP-1", "1920x1200@59.950", {})]),
            (1920, 0, 1.0, 0, False, [("HDMI-1", "2560x1440@59.950", {})]),
        ]
        expected_logical_monitors = GLib.Variant(
            "(uua(iiduba(ssa{sv}))a{sv})",
            (
                1,
                1,
                logical_monitors,
                {},
            ),
        )
        mock_proxy.call_sync.assert_called_with(
            method_name="ApplyMonitorsConfig",
            parameters=expected_logical_monitors,
            flags=Gio.DBusCallFlags.NONE,
            timeout_msec=-1,
            cancellable=None,
        )
