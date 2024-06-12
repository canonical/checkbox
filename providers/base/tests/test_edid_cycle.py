"""This module provides test cases for the edid_cycle module."""

import unittest
import textwrap
from pathlib import Path
from unittest.mock import patch, call, Mock
from gi.repository import GLib, Gio

import edid_cycle


class MonitorConfigDBusTests(unittest.TestCase):
    """This class provides test cases for the MonitorCOnfig DBus class."""

    @patch("edid_cycle.Gio.DBusProxy")
    def test_get_current_resolution(self, mock_dbus_proxy):
        """
        Test whether the function returns a dictionary of
        monitor-id:resolution for any active monitors.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        monitor_config = edid_cycle.MonitorConfigDBus()
        mock_proxy.call_sync.return_value = GLib.Variant(
            "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})",
            (
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
                            "display-name": GLib.Variant(
                                "s", "Built-in display"
                            ),
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
                            "display-name": GLib.Variant(
                                "s", "External Display"
                            ),
                        },
                    ),
                ],
                [],
                {},
            ),
        )
        resolutions = monitor_config.get_current_resolutions()
        self.assertEqual(
            resolutions, {"eDP-1": "1920x1200", "HDMI-1": "2560x1440"}
        )

    @patch("edid_cycle.Gio.DBusProxy")
    def test_set_extended_mode(self, mock_dbus_proxy):
        """
        Test whether the function set the logical display
        configuration to two screens at maximum resolution
        placed horizontally.
        """

        mock_proxy = Mock()
        mock_dbus_proxy.new_for_bus_sync.return_value = mock_proxy

        monitor_config = edid_cycle.MonitorConfigDBus()
        mock_proxy.call_sync.return_value = GLib.Variant(
            "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})",
            (
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
                            "display-name": GLib.Variant(
                                "s", "Built-in display"
                            ),
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
                            "display-name": GLib.Variant(
                                "s", "External Display"
                            ),
                        },
                    ),
                ],
                [],
                {},
            ),
        )
        monitor_config.set_extended_mode()

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
            Monitors: 1
             0: +HDMI-1 1920/576x1080/324+800+1080 HDMI-1
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

    @patch("edid_cycle.zapper_monitor")
    @patch("edid_cycle.test_edid")
    @patch("edid_cycle.discover_video_output_device")
    def test_main(self, mock_discover, mock_test_edid, mock_monitor):
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
