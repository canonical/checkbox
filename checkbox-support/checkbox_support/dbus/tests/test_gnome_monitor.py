import re
import sys
import unittest
from unittest.mock import patch, Mock, MagicMock

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

from gi.repository import GLib, Gio  # type: ignore
from checkbox_support.dbus.gnome_monitor import MonitorConfigGnome


class MonitorConfigGnomeTests(unittest.TestCase):
    """This class provides test cases for the MonitorConfig DBus class."""

    class MockGetCurrentStateReturnValue:

        class MockGLibType:
            def __init__(self, equal_check_return_value):
                self.rv = equal_check_return_value

            def equal(self, other):
                return self.rv

        def __init__(self, type_val, type_check_return_value=True):
            self.type_val = type_val
            self.type_check_return_value = type_check_return_value

        def __getitem__(self, key):
            return self.type_val[key]

        def get_type(self):
            return self.MockGLibType(self.type_check_return_value)

    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_get_connected_monitors(self, mock_dbus_proxy):
        """
        Test whether the function returns a list of connected
        monitors, even if inactive.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()
        raw = (
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
                                "is-current": GLib.Variant("b", False),
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
        mock_proxy.call_sync.return_value = (
            self.MockGetCurrentStateReturnValue(raw)
        )
        monitors = gnome_monitor.get_connected_monitors()
        self.assertSetEqual(monitors, {"eDP-1", "HDMI-1"})

    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_get_current_resolution(self, mock_dbus_proxy):
        """
        Test whether the function returns a dictionary of
        monitor-id:resolution for any active monitors.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()

        raw = (
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
        mock_proxy.call_sync.return_value = (
            self.MockGetCurrentStateReturnValue(raw)
        )
        resolutions = gnome_monitor.get_current_resolutions()
        self.assertEqual(
            resolutions, {"eDP-1": "1920x1200", "HDMI-1": "2560x1440"}
        )

    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_bad_input_type(self, mock_dbus_proxy):
        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()
        mock_proxy.call_sync.return_value = (
            self.MockGetCurrentStateReturnValue(tuple(), False)
        )
        self.assertRaises(TypeError, gnome_monitor.get_current_state)

    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_set_extended_mode(self, mock_dbus_proxy):
        """
        Test whether the function set the logical display
        configuration to two screens at preferred resolution
        placed horizontally.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()
        raw = (
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
                                "is-preferred": GLib.Variant("b", False),
                            },
                        ),
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
        mock_proxy.call_sync.return_value = (
            self.MockGetCurrentStateReturnValue(raw)
        )
        configuration = gnome_monitor.set_extended_mode()

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
        expected = {
            "eDP-1": "1920x1200",
            "HDMI-1": "2560x1440",
        }
        self.assertDictEqual(configuration, expected)

    @patch("time.sleep")
    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_cycle(self, mock_dbus_proxy: MagicMock, _):
        """
        Test the cycle could get the right monitors configuration
        and send to ApplyMonitorsConfig.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()

        raw = (
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
        mock_proxy.call_sync.return_value = (
            self.MockGetCurrentStateReturnValue(raw)
        )
        gnome_monitor.cycle()

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

    @patch("time.sleep")
    @patch("checkbox_support.dbus.gnome_monitor.Gio.DBusProxy")
    def test_cycle_no_cycling(self, mock_dbus_proxy: MagicMock, _):
        """
        Test the cycle could get the right monitors configuration
        (without res and transform change) and send to ApplyMonitorsConfig.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()
        raw = (
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
        mock_proxy.call_sync.return_value = (
            self.MockGetCurrentStateReturnValue(raw)
        )
        # mock callback
        mock_resolution_filter = MagicMock()
        mock_resolution_filter.side_effect = (
            lambda x: x
        )  # keep the real mode values
        mock_post_cycle_action = MagicMock()
        gnome_monitor.cycle(
            cycle_resolutions=False,
            cycle_transforms=False,
            resolution_filter=mock_resolution_filter,
            post_cycle_action=mock_post_cycle_action,
        )

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
        argument_string = mock_post_cycle_action.call_args[0][0]
        p1 = "HDMI-1_2560x1440_normal_"
        p2 = "eDP-1_1920x1200_normal_"
        pattern = re.compile("{}{}|{}{}".format(p1, p2, p2, p1))
        assert pattern.match(argument_string)


if __name__ == "__main__":
    unittest.main()
