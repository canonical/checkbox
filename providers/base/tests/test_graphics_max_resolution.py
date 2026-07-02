#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
#
# Authors:
#   Zhongning Li <zhongning.li@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from graphics_max_resolution import SysfsDrmCardInfo, main


def _make_drm_port(
    base_dir: str,
    port_name: str,
    mode: str,
    enabled: str,
    status: str,
    dpms: str,
):
    port_dir = Path(base_dir) / port_name
    port_dir.mkdir()
    (port_dir / "modes").write_text(mode)
    (port_dir / "enabled").write_text(enabled)
    (port_dir / "status").write_text(status)
    (port_dir / "dpms").write_text(dpms)
    return port_dir


class TestSysfsDrmCardInfoInit(unittest.TestCase):
    def test_raises_when_path_is_not_a_directory(self):
        with TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "not_a_dir"
            file_path.touch()
            with self.assertRaises(ValueError):
                SysfsDrmCardInfo(file_path)

    def test_raises_when_modes_file_is_empty(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp, "card1-eDP-1", "", "enabled", "connected", "On"
            )
            with self.assertRaises(ValueError):
                SysfsDrmCardInfo(port_dir)

    def test_parses_max_resolution_from_first_line(self):
        with TemporaryDirectory() as tmp:
            # modes file has multiple resolutions; only the first matters
            port_dir = _make_drm_port(
                tmp,
                "card1-eDP-1",
                "1920x1080\n1280x720\n",
                "enabled",
                "connected",
                "On",
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertEqual(info.max_width, 1920)
            self.assertEqual(info.max_height, 1080)

    def test_enabled_true(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp, "card1-eDP-1", "1920x1080\n", "enabled", "connected", "On"
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertTrue(info.enabled)

    def test_enabled_false(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp,
                "card1-eDP-1",
                "1920x1080\n",
                "disabled",
                "connected",
                "On",
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertFalse(info.enabled)

    def test_is_connected_true(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp, "card1-eDP-1", "1920x1080\n", "enabled", "connected", "On"
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertTrue(info.is_connected)

    def test_is_connected_false(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp,
                "card1-eDP-1",
                "1920x1080\n",
                "enabled",
                "disconnected",
                "On",
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertFalse(info.is_connected)

    def test_dpms_enabled_true(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp, "card1-eDP-1", "1920x1080\n", "enabled", "connected", "On"
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertTrue(info.dpms_enabled)

    def test_dpms_enabled_false(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp,
                "card1-eDP-1",
                "1920x1080\n",
                "enabled",
                "connected",
                "Off",
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertFalse(info.dpms_enabled)

    def test_port_name_is_set(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp,
                "card1-HDMI-A-1",
                "2560x1440\n",
                "enabled",
                "connected",
                "On",
            )
            info = SysfsDrmCardInfo(port_dir)
            self.assertEqual(info.port, "card1-HDMI-A-1")


class TestSysfsDrmCardInfoStr(unittest.TestCase):
    def test_str_contains_all_fields(self):
        with TemporaryDirectory() as tmp:
            port_dir = _make_drm_port(
                tmp,
                "card1-eDP-1",
                "1920x1080\n",
                "enabled",
                "connected",
                "On",
            )
            info = SysfsDrmCardInfo(port_dir)
            result = str(info)
            self.assertIn("card1-eDP-1", result)
            self.assertIn("1920", result)
            self.assertIn("1080", result)
            self.assertIn("True", result)


class TestGetAllActivePorts(unittest.TestCase):
    def test_returns_only_valid_ports(self):
        with TemporaryDirectory() as tmp:
            # One valid port, one port with no monitor (empty modes → ValueError)
            valid_port = _make_drm_port(
                tmp,
                "card1-eDP-1",
                "1920x1080\n",
                "enabled",
                "connected",
                "On",
            )
            empty_port = _make_drm_port(
                tmp, "card1-DP-1", "", "enabled", "disconnected", "Off"
            )
            fake_paths = [str(valid_port), str(empty_port)]
            with patch(
                "graphics_max_resolution.glob", return_value=fake_paths
            ):
                ports = SysfsDrmCardInfo.get_all_active_ports()
            self.assertEqual(len(ports), 1)
            self.assertEqual(ports[0].port, "card1-eDP-1")

    def test_returns_empty_list_when_no_ports(self):
        with patch("graphics_max_resolution.glob", return_value=[]):
            ports = SysfsDrmCardInfo.get_all_active_ports()
        self.assertEqual(ports, [])


def _make_monitor(vendor, product, connector, curr_w, curr_h, max_w, max_h):
    """Build a mock PhysicalMonitor for use in main() tests."""
    monitor = MagicMock()
    monitor.info.vendor = vendor
    monitor.info.product = product
    monitor.info.connector = connector

    if curr_w is None:
        monitor.get_current_mode.return_value = None
    else:
        curr_mode = MagicMock()
        curr_mode.width = curr_w
        curr_mode.height = curr_h
        monitor.get_current_mode.return_value = curr_mode

    monitor.get_max_resolution.return_value = (max_w, max_h)
    return monitor


def _make_drm_card(max_w, max_h, enabled=True):
    """Build a mock SysfsDrmCardInfo."""
    card = MagicMock(spec=SysfsDrmCardInfo)
    card.max_width = max_w
    card.max_height = max_h
    card.enabled = enabled
    return card


class TestMain(unittest.TestCase):
    def _run_main(self, monitors, drm_cards):
        """Patch dependencies and call main(), returning captured stdout."""
        mutter_state = MagicMock()
        mutter_state.physical_monitors = monitors

        with (
            patch("graphics_max_resolution.MonitorConfigGnome") as MockGnome,
            patch(
                "graphics_max_resolution.SysfsDrmCardInfo.get_all_active_ports",
                return_value=drm_cards,
            ),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
        ):
            MockGnome.return_value.get_current_state.return_value = (
                mutter_state
            )
            main()
            return mock_stdout.getvalue()

    def test_single_monitor_at_max_resolution_passes(self):
        monitors = [
            _make_monitor(
                "BOE", "NE135A1M-NY1", "eDP-1", 1920, 1080, 1920, 1080
            )
        ]
        drm_cards = [_make_drm_card(1920, 1080, enabled=True)]
        output = self._run_main(monitors, drm_cards)
        self.assertIn("[ OK ]", output)
        self.assertIn("1920x1080", output)

    def test_monitor_below_max_resolution_raises_system_exit(self):
        monitors = [
            _make_monitor(
                "BOE", "NE135A1M-NY1", "eDP-1", 1280, 720, 1920, 1080
            )
        ]
        with self.assertRaises(SystemExit):
            self._run_main(monitors, [])

    def test_monitor_below_max_resolution_prints_error(self):
        monitors = [
            _make_monitor(
                "BOE", "NE135A1M-NY1", "eDP-1", 1280, 720, 1920, 1080
            )
        ]
        mutter_state = MagicMock()
        mutter_state.physical_monitors = monitors

        with (
            patch("graphics_max_resolution.MonitorConfigGnome") as MockGnome,
            patch("sys.stderr", new_callable=StringIO) as mock_err,
        ):
            MockGnome.return_value.get_current_state.return_value = (
                mutter_state
            )
            with self.assertRaises(SystemExit):
                main()
            self.assertIn("[ ERR ]", mock_err.getvalue())
            self.assertIn("1920x1080", mock_err.getvalue())

    def test_inactive_monitor_is_skipped(self):
        # curr mode is None → should print WARN and continue
        monitors = [
            _make_monitor(
                "BOE", "NE135A1M-NY1", "eDP-1", None, None, 1920, 1080
            )
        ]
        drm_cards = []
        output = self._run_main(monitors, drm_cards)
        self.assertIn("WARN", output)

    def test_gnome_sysfs_resolution_mismatch_raises_system_exit(self):
        # GNOME sees 1920x1080 but sysfs reports 2560x1440
        monitors = [
            _make_monitor(
                "BOE", "NE135A1M-NY1", "eDP-1", 1920, 1080, 1920, 1080
            )
        ]
        drm_cards = [_make_drm_card(2560, 1440, enabled=True)]
        with self.assertRaises(SystemExit):
            self._run_main(monitors, drm_cards)

    def test_disabled_drm_cards_excluded_from_sysfs_total(self):
        # Monitor at 1920x1080 in GNOME; sysfs has a matching enabled card
        # plus a disabled card that must NOT be counted
        monitors = [
            _make_monitor(
                "BOE", "NE135A1M-NY1", "eDP-1", 1920, 1080, 1920, 1080
            )
        ]
        drm_cards = [
            _make_drm_card(1920, 1080, enabled=True),
            _make_drm_card(3840, 2160, enabled=False),
        ]
        # Should pass because the disabled card is excluded
        output = self._run_main(monitors, drm_cards)
        self.assertIn("matches sysfs", output)

    def test_multiple_monitors_all_at_max_passes(self):
        monitors = [
            _make_monitor(
                "BOE", "NE135A1M-NY1", "eDP-1", 1920, 1080, 1920, 1080
            ),
            _make_monitor("DEL", "U2722D", "HDMI-1", 2560, 1440, 2560, 1440),
        ]
        drm_cards = [
            _make_drm_card(1920, 1080, enabled=True),
            _make_drm_card(2560, 1440, enabled=True),
        ]
        output = self._run_main(monitors, drm_cards)
        self.assertIn("matches sysfs", output)

    def test_no_monitors_passes(self):
        # No monitors → nothing to fail, sysfs total also 0 → OK
        output = self._run_main([], [])
        self.assertIn("matches sysfs", output)


if __name__ == "__main__":
    unittest.main()
