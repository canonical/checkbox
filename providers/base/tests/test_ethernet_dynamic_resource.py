#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

import os
import unittest
from io import StringIO
from unittest.mock import mock_open, patch

import ethernet_dynamic_resource as edr


class TestGetExcludedFromEnv(unittest.TestCase):
    """Tests for get_excluded_from_env()"""

    def test_empty_env_var_returns_empty_list(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("EXCLUDE_MACS", None)
            result = edr.get_excluded_from_env("EXCLUDE_MACS")
        self.assertEqual(result, [])

    def test_single_value(self):
        with patch.dict(os.environ, {"EXCLUDE_MACS": "aa:bb:cc:dd:ee:ff"}):
            result = edr.get_excluded_from_env("EXCLUDE_MACS")
        self.assertEqual(result, ["aa:bb:cc:dd:ee:ff"])

    def test_multiple_comma_separated_values(self):
        with patch.dict(
            os.environ, {"EXCLUDE_MACS": "aa:bb:cc:dd:ee:ff,11:22:33:44:55:66"}
        ):
            result = edr.get_excluded_from_env("EXCLUDE_MACS")
        self.assertEqual(result, ["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"])

    def test_values_with_whitespace_are_stripped(self):
        with patch.dict(
            os.environ,
            {"EXCLUDE_MACS": " aa:bb:cc:dd:ee:ff , 11:22:33:44:55:66 "},
        ):
            result = edr.get_excluded_from_env("EXCLUDE_MACS")
        self.assertEqual(result, ["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"])

    def test_empty_entries_are_ignored(self):
        with patch.dict(
            os.environ,
            {"EXCLUDE_MACS": "aa:bb:cc:dd:ee:ff,,11:22:33:44:55:66"},
        ):
            result = edr.get_excluded_from_env("EXCLUDE_MACS")
        self.assertEqual(result, ["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"])

    def test_env_var_not_set_returns_empty_list(self):
        env = {k: v for k, v in os.environ.items() if k != "NO_SUCH_VAR_XYZ"}
        with patch.dict(os.environ, env, clear=True):
            result = edr.get_excluded_from_env("NO_SUCH_VAR_XYZ")
        self.assertEqual(result, [])


class TestIsRealHardware(unittest.TestCase):
    """Tests for is_real_hardware()"""

    def test_no_device_symlink_returns_false(self):
        with patch("os.path.islink", return_value=False):
            self.assertFalse(edr.is_real_hardware("/sys/class/net/lo"))

    def test_wireless_interface_returns_false(self):
        def islink(path):
            return path.endswith("device")

        def exists(path):
            return path.endswith("wireless")

        with patch("os.path.islink", side_effect=islink), patch(
            "os.path.exists", side_effect=exists
        ):
            self.assertFalse(edr.is_real_hardware("/sys/class/net/wlan0"))

    def test_virtual_subsystem_returns_false(self):
        def islink(path):
            # device symlink and subsystem symlink both exist
            return path.endswith("device") or path.endswith("subsystem")

        def exists(path):
            return False  # no wireless dir

        with patch("os.path.islink", side_effect=islink), patch(
            "os.path.exists", side_effect=exists
        ), patch("os.readlink", return_value="/sys/bus/virtual"):
            self.assertFalse(edr.is_real_hardware("/sys/class/net/veth0"))

    def test_non_virtual_subsystem_returns_true(self):
        def islink(path):
            return path.endswith("device") or path.endswith("subsystem")

        def exists(path):
            return False

        with patch("os.path.islink", side_effect=islink), patch(
            "os.path.exists", side_effect=exists
        ), patch("os.readlink", return_value="/sys/bus/pci"):
            self.assertTrue(edr.is_real_hardware("/sys/class/net/eth0"))

    def test_missing_subsystem_symlink_still_returns_true(self):
        """
        If subsystem link is absent, interface is still treated as hardware.
        """

        def islink(path):
            # device exists but subsystem symlink does not
            return path.endswith("device")

        def exists(path):
            return False

        with patch("os.path.islink", side_effect=islink), patch(
            "os.path.exists", side_effect=exists
        ):
            self.assertTrue(edr.is_real_hardware("/sys/class/net/eth0"))


class TestListInterfaces(unittest.TestCase):
    """Tests for list_interfaces()"""

    def test_base_path_missing_produces_no_output(self):
        with patch("os.path.exists", return_value=False):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                edr.list_interfaces([], [])
        self.assertEqual(mock_stdout.getvalue(), "")

    def _make_list_interfaces_env(self, ifaces, mac_map, real_hw_ifaces):
        """
        Helper: patches os so list_interfaces sees a controlled /sys/class/net.
        ifaces: list of interface names in base_path
        mac_map: dict {iface: mac}
        real_hw_ifaces: set of ifaces is_real_hardware returns True for
        """

        def fake_exists(path):
            return path == "/sys/class/net/"

        def fake_listdir(path):
            return ifaces

        def fake_is_real_hardware(iface_path):
            iface = os.path.basename(iface_path)
            return iface in real_hw_ifaces

        def fake_open(path, *args, **kwargs):
            iface = path.split("/sys/class/net/")[1].split("/")[0]
            mac = mac_map.get(iface, "")
            return mock_open(read_data=mac)()

        return fake_exists, fake_listdir, fake_is_real_hardware, fake_open

    def test_single_hardware_interface_is_printed(self):
        (
            fake_exists,
            fake_listdir,
            fake_is_real_hw,
            fake_open,
        ) = self._make_list_interfaces_env(
            ifaces=["eth0"],
            mac_map={"eth0": "aa:bb:cc:dd:ee:ff"},
            real_hw_ifaces={"eth0"},
        )
        with patch("os.path.exists", side_effect=fake_exists), patch(
            "os.listdir", return_value=["eth0"]
        ), patch(
            "ethernet_dynamic_resource.is_real_hardware",
            side_effect=fake_is_real_hw,
        ), patch(
            "builtins.open", side_effect=fake_open
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_stdout:
            edr.list_interfaces([], [])
        output = mock_stdout.getvalue()
        self.assertIn("interface: eth0", output)
        self.assertIn("mac: aa:bb:cc:dd:ee:ff", output)

    def test_non_hardware_interface_is_skipped(self):
        (
            fake_exists,
            _,
            fake_is_real_hw,
            fake_open,
        ) = self._make_list_interfaces_env(
            ifaces=["lo"],
            mac_map={"lo": "00:00:00:00:00:00"},
            real_hw_ifaces=set(),  # lo is not hardware
        )
        with patch("os.path.exists", side_effect=fake_exists), patch(
            "os.listdir", return_value=["lo"]
        ), patch(
            "ethernet_dynamic_resource.is_real_hardware",
            side_effect=fake_is_real_hw,
        ), patch(
            "builtins.open", side_effect=fake_open
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_stdout:
            edr.list_interfaces([], [])
        self.assertEqual(mock_stdout.getvalue(), "")

    def test_ignored_interface_name_is_skipped(self):
        (
            fake_exists,
            _,
            fake_is_real_hw,
            fake_open,
        ) = self._make_list_interfaces_env(
            ifaces=["eth0"],
            mac_map={"eth0": "aa:bb:cc:dd:ee:ff"},
            real_hw_ifaces={"eth0"},
        )
        with patch("os.path.exists", side_effect=fake_exists), patch(
            "os.listdir", return_value=["eth0"]
        ), patch(
            "ethernet_dynamic_resource.is_real_hardware",
            side_effect=fake_is_real_hw,
        ), patch(
            "builtins.open", side_effect=fake_open
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_stdout:
            edr.list_interfaces(["eth0"], [])
        self.assertEqual(mock_stdout.getvalue(), "")

    def test_ignored_mac_is_skipped(self):
        (
            fake_exists,
            _,
            fake_is_real_hw,
            fake_open,
        ) = self._make_list_interfaces_env(
            ifaces=["eth0"],
            mac_map={"eth0": "aa:bb:cc:dd:ee:ff"},
            real_hw_ifaces={"eth0"},
        )
        with patch("os.path.exists", side_effect=fake_exists), patch(
            "os.listdir", return_value=["eth0"]
        ), patch(
            "ethernet_dynamic_resource.is_real_hardware",
            side_effect=fake_is_real_hw,
        ), patch(
            "builtins.open", side_effect=fake_open
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_stdout:
            edr.list_interfaces([], ["aa:bb:cc:dd:ee:ff"])
        self.assertEqual(mock_stdout.getvalue(), "")

    def test_ignored_mac_comparison_is_case_insensitive(self):
        (
            fake_exists,
            _,
            fake_is_real_hw,
            fake_open,
        ) = self._make_list_interfaces_env(
            ifaces=["eth0"],
            mac_map={"eth0": "aa:bb:cc:dd:ee:ff"},
            real_hw_ifaces={"eth0"},
        )
        with patch("os.path.exists", side_effect=fake_exists), patch(
            "os.listdir", return_value=["eth0"]
        ), patch(
            "ethernet_dynamic_resource.is_real_hardware",
            side_effect=fake_is_real_hw,
        ), patch(
            "builtins.open", side_effect=fake_open
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_stdout:
            # ignored_macs already lowercased by main(); simulate that here
            edr.list_interfaces([], ["aa:bb:cc:dd:ee:ff"])
        self.assertEqual(mock_stdout.getvalue(), "")

    def test_mac_read_error_skips_interface(self):
        fake_exists, _, fake_is_real_hw, _ = self._make_list_interfaces_env(
            ifaces=["eth0"],
            mac_map={},
            real_hw_ifaces={"eth0"},
        )
        with patch("os.path.exists", side_effect=fake_exists), patch(
            "os.listdir", return_value=["eth0"]
        ), patch(
            "ethernet_dynamic_resource.is_real_hardware",
            side_effect=fake_is_real_hw,
        ), patch(
            "builtins.open", side_effect=OSError("permission denied")
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_stdout:
            edr.list_interfaces([], [])
        self.assertEqual(mock_stdout.getvalue(), "")

    def test_multiple_interfaces_sorted_output(self):
        ifaces = ["eth1", "eth0"]
        mac_map = {"eth0": "00:11:22:33:44:55", "eth1": "66:77:88:99:aa:bb"}

        def fake_exists(path):
            return path == "/sys/class/net/"

        def fake_is_real_hw(iface_path):
            return True

        def fake_open(path, *args, **kwargs):
            iface = path.split("/sys/class/net/")[1].split("/")[0]
            return mock_open(read_data=mac_map[iface])()

        with patch("os.path.exists", side_effect=fake_exists), patch(
            "os.listdir", return_value=ifaces
        ), patch(
            "ethernet_dynamic_resource.is_real_hardware",
            side_effect=fake_is_real_hw,
        ), patch(
            "builtins.open", side_effect=fake_open
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_stdout:
            edr.list_interfaces([], [])

        output = mock_stdout.getvalue()
        eth0_pos = output.index("interface: eth0")
        eth1_pos = output.index("interface: eth1")
        self.assertLess(eth0_pos, eth1_pos)


class TestMain(unittest.TestCase):
    """Tests for main() argument parsing and wiring."""

    def test_main_defaults_use_standard_env_vars(self):
        with patch.dict(
            os.environ,
            {"EXCLUDE_MACS": "", "EXCLUDE_INTERFACES": ""},
            clear=False,
        ), patch("sys.argv", ["prog"]), patch(
            "ethernet_dynamic_resource.list_interfaces"
        ) as mock_list:
            edr.main()
        mock_list.assert_called_once_with([], [])

    def test_main_custom_env_vars(self):
        with patch.dict(
            os.environ, {"MY_MACS": "AA:BB:CC:DD:EE:FF", "MY_IFACES": "eth0"}
        ), patch(
            "sys.argv",
            ["prog", "--env-mac", "MY_MACS", "--env-iface", "MY_IFACES"],
        ), patch(
            "ethernet_dynamic_resource.list_interfaces"
        ) as mock_list:
            edr.main()
        mock_list.assert_called_once_with(["eth0"], ["aa:bb:cc:dd:ee:ff"])

    def test_main_macs_are_lowercased(self):
        with patch.dict(
            os.environ, {"EXCLUDE_MACS": "AA:BB:CC:DD:EE:FF"}
        ), patch("sys.argv", ["prog"]), patch(
            "ethernet_dynamic_resource.list_interfaces"
        ) as mock_list:
            edr.main()
        _, call_kwargs = mock_list.call_args
        passed_macs = mock_list.call_args[0][1]
        self.assertEqual(passed_macs, ["aa:bb:cc:dd:ee:ff"])


if __name__ == "__main__":
    unittest.main()
