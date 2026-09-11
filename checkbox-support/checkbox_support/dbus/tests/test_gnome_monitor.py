import re
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

from checkbox_support.dbus.gnome_monitor import (
    MonitorConfigGnome,
    MonitorInfo,
    MutterDisplayMode,
    PhysicalMonitor,
)
from gi.repository import Gio, GLib  # type: ignore


def make_mode(
    width: int,
    height: int,
    is_current: bool = False,
    mode_id: "str | None" = None,
):
    if mode_id is None:
        mode_id = f"{width}x{height}"
    return MutterDisplayMode(
        mode_id,
        width,
        height,
        60.0,
        1.0,
        [1.0],
        {"is-current": is_current, "is-preferred": False},
    )


def make_physical_monitor(
    modes: "list[MutterDisplayMode]", connector: str = "eDP-1"
):
    return PhysicalMonitor(
        MonitorInfo(connector, "LGD", "0x06b3", "0x00000000"),
        modes,
        {},
    )


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
    def test_get_current_resolution_excludes_non_current(
        self, mock_dbus_proxy
    ):
        """
        Test that get_current_resolutions only returns resolutions
        for modes that are marked as current.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        gnome_monitor = MonitorConfigGnome()

        # Use plain booleans instead of GLib.Variant since GLib is
        # mocked; the code accesses properties via dict.get() so plain
        # values work correctly and let us test truthy/falsy behavior.
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
                                "is-current": True,
                                "is-preferred": True,
                            },
                        ),
                        (
                            "1280x720@60.000",
                            1280,
                            720,
                            60.0,
                            1.0,
                            [1.0],
                            {
                                "is-current": False,
                                "is-preferred": False,
                            },
                        ),
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
                                "is-current": False,
                                "is-preferred": True,
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
        # Only eDP-1's current mode should appear;
        # HDMI-1 has no current mode and eDP-1's non-current mode is excluded
        self.assertEqual(resolutions, {"eDP-1": "1920x1200"})

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

    @patch("checkbox_support.dbus.gnome_monitor.sleep")
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

    @patch("checkbox_support.dbus.gnome_monitor.sleep")
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
        pattern = re.compile(f"{p1}{p2}|{p2}{p1}")
        assert pattern.match(argument_string)


class PhysicalMonitorTests(unittest.TestCase):

    def test_get_current_mode_returns_current(self):
        current_mode = make_mode(1920, 1200, is_current=True)
        monitor = make_physical_monitor([make_mode(1280, 720), current_mode])
        self.assertEqual(monitor.get_current_mode(), current_mode)

    def test_get_current_mode_returns_none_if_no_mode_is_current(self):
        monitor = make_physical_monitor(
            [make_mode(1280, 720), make_mode(1920, 1200)]
        )
        self.assertIsNone(monitor.get_current_mode())

    def test_get_current_mode_returns_none_if_no_modes(self):
        monitor = make_physical_monitor([])
        self.assertIsNone(monitor.get_current_mode())

    def test_get_max_resolution_picks_largest_mode(self):
        monitor = make_physical_monitor(
            [
                make_mode(1280, 720),
                make_mode(1920, 1200),
                make_mode(1024, 768),
            ]
        )
        self.assertEqual(monitor.get_max_resolution(), (1920, 1200))

    def test_get_max_resolution_raises_value_error_if_no_modes(self):
        monitor = make_physical_monitor([])
        self.assertRaises(ValueError, monitor.get_max_resolution)

    def test_get_max_resolution_raises_runtime_error_if_all_zero(self):
        monitor = make_physical_monitor([make_mode(0, 0), make_mode(0, 0)])
        self.assertRaises(RuntimeError, monitor.get_max_resolution)


if __name__ == "__main__":
    unittest.main()
