#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2025 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import textwrap
import unittest
from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open, ANY
import datetime
import subprocess as sp
import io
import sys
from unittest.mock import call
from eth_hotplugging import (
    netplan_renderer,
    get_interface_info,
    _check_routable_state,
    wait_for_routable_state,
    has_cable,
    wait_for_cable_state,
    help_wait_cable_and_routable_state,
    main,
)

from checkbox_support.helpers.retry import mock_retry


class EthHotpluggingTests(TestCase):
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="network:\n  renderer: networkd",
    )
    @patch("os.path.exists", return_value=True)
    @patch("glob.glob", return_value=["/etc/netplan/01-netcfg.yaml"])
    def test_renderer_networkd(self, mock_exists, mock_glob, mock_open):
        renderer = netplan_renderer()
        self.assertEqual(renderer, "networkd")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="network:\n  abc: def",
    )
    @patch("os.path.exists", return_value=True)
    @patch("glob.glob", return_value=["/etc/netplan/01-netcfg.yaml"])
    def test_renderer_networkd_no_renderer(
        self, mock_exists, mock_glob, mock_open
    ):
        renderer = netplan_renderer()
        self.assertEqual(renderer, "networkd")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="network:\n  renderer: NetworkManager",
    )
    @patch("glob.glob", return_value=["/etc/netplan/01-netcfg.yaml"])
    @patch("os.path.exists", return_value=True)
    def test_renderer_networkmanager(self, mock_exists, mock_glob, mock_open):
        renderer = netplan_renderer()
        self.assertEqual(renderer, "NetworkManager")

    @patch("glob.glob", return_value=[])
    @patch("os.path.exists", return_value=True)
    def test_no_yaml_files(self, mock_exists, mock_glob):
        renderer = netplan_renderer()
        self.assertEqual(renderer, "NetworkManager")

    @patch("subprocess.check_output")
    def test_get_interface_info_networkd(self, mock_check_output):
        mock_check_output.return_value = (
            "State: routable\nGateway: 192.168.1.1\nPath: pci-0000:02:00.0"
        )
        interface = "eth0"
        renderer = "networkd"
        info = get_interface_info(interface, renderer)
        self.assertEqual(info["state"], "routable")
        self.assertEqual(info["gateway"], "192.168.1.1")

    @patch("subprocess.check_output")
    def test_get_interface_info_networkd_any_name(self, mock_check_output):
        mock_check_output.return_value = (
            "State: routable\nGateway: 192.168.1.1 (ABC 123)\n"
            "Path: pci-0000:02:00.0"
        )
        interface = "eth0"
        renderer = "networkd"
        info = get_interface_info(interface, renderer)
        self.assertEqual(info["state"], "routable")
        self.assertEqual(info["gateway"], "192.168.1.1 (ABC 123)")

    @patch("subprocess.check_output")
    def test_get_interface_info_networkd_no_state(self, mock_check_output):
        mock_check_output.return_value = (
            "Some other info: value\nsome more info"
        )
        interface = "eth0"
        renderer = "networkd"
        info = get_interface_info(interface, renderer)
        self.assertNotIn("state", info)
        self.assertNotIn("gateway", info)

    @patch("subprocess.check_output")
    def test_get_interface_info_networkd_empty_output(self, mock_check_output):
        mock_check_output.return_value = " "
        interface = "eth0"
        renderer = "networkd"
        info = get_interface_info(interface, renderer)
        self.assertEqual(info, {})

    @patch(
        "subprocess.check_output",
        side_effect=sp.CalledProcessError(1, "Command failed"),
    )
    def test_get_interface_info_networkd_command_fails(
        self, mock_check_output
    ):
        interface = "eth0"
        renderer = "networkd"
        with self.assertRaises(SystemExit) as cm:
            get_interface_info(interface, renderer)
        self.assertIn(
            "Error running command "
            "'networkctl status --no-pager --no-legend eth0' "
            "for renderer 'networkd':",
            str(cm.exception),
        )

    @patch("subprocess.check_output")
    def test_get_interface_info_networkmanager(self, mock_check_output):
        mock_check_output.return_value = (
            "GENERAL.MTU:                            1500\n"
            "GENERAL.STATE:                          100 (connected)\n"
            "IP4.GATEWAY:                            192.168.1.1"
        )
        interface = "eth0"
        renderer = "NetworkManager"
        info = get_interface_info(interface, renderer)
        self.assertEqual(info["state"], "100 (connected)")
        self.assertEqual(info["gateway"], "192.168.1.1")

    @patch("subprocess.check_output")
    def test_get_interface_info_networkmanager_unexpected_output(
        self, mock_check_output
    ):
        mock_check_output.return_value = "some unexpected output"
        interface = "eth0"
        renderer = "NetworkManager"
        info = get_interface_info(interface, renderer)
        self.assertEqual(info, {})

    @patch(
        "subprocess.check_output",
        side_effect=sp.CalledProcessError(1, "Command failed"),
    )
    def test_get_interface_info_networkmanager_command_fails(
        self, mock_check_output
    ):
        interface = "eth0"
        renderer = "NetworkManager"
        with self.assertRaises(SystemExit) as cm:
            get_interface_info(interface, renderer)
        self.assertIn(
            "Error running command 'nmcli device show eth0' "
            "for renderer 'NetworkManager':",
            str(cm.exception),
        )

    def test_get_interface_info_unknown_renderer(self):
        interface = "eth0"
        renderer = "unknown"
        with self.assertRaises(ValueError):
            get_interface_info(interface, renderer)

    @patch(
        "eth_hotplugging.get_interface_info",
        return_value={"state": "routable"},
    )
    def test_check_routable_state_networkd(self, mock_get_interface_info):
        renderer = "networkd"
        self.assertTrue(_check_routable_state("eth0", renderer))

    @patch(
        "eth_hotplugging.get_interface_info",
        return_value={"state": "connected"},
    )
    def test_check_routable_state_networkmanager(
        self, mock_get_interface_info
    ):
        renderer = "NetworkManager"
        self.assertTrue(_check_routable_state("eth0", renderer))

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="1",
    )
    def test_has_cable_true(self, mock_open):
        result = has_cable("eth0")
        self.assertTrue(result)
        mock_open.assert_called_once_with("/sys/class/net/eth0/carrier")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="0",
    )
    def test_has_cable_false(self, mock_open):
        result = has_cable("eth0")
        self.assertFalse(result)
        mock_open.assert_called_once_with("/sys/class/net/eth0/carrier")

    @patch("eth_hotplugging.netplan_renderer", return_value="networkd")
    @patch("eth_hotplugging.has_cable", return_value=True)
    @patch(
        "eth_hotplugging._check_routable_state",
        return_value=(True, "routable"),
    )
    def test_help_wait_cable_and_routable_state_true(
        self,
        mock_check_routable_state,
        mock_has_cable,
        mock_netplan_renderer,
    ):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        help_wait_cable_and_routable_state("eth0", do_check=True)
        sys.stdout = sys.__stdout__
        self.assertIn("Cable connected!", captured_output.getvalue())
        self.assertIn("Network routable!", captured_output.getvalue())

    @patch("eth_hotplugging.netplan_renderer", return_value="NetworkManager")
    @patch("eth_hotplugging.has_cable", return_value=False)
    @patch(
        "eth_hotplugging._check_routable_state",
        return_value=(False, "routable"),
    )
    def test_help_wait_cable_and_routable_state_false(
        self,
        mock_check_routable_state,
        mock_has_cable,
        mock_netplan_renderer,
    ):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        help_wait_cable_and_routable_state("eth0", do_check=False)
        sys.stdout = sys.__stdout__
        self.assertIn("Cable disconnected!", captured_output.getvalue())
        self.assertIn("Network NOT routable!", captured_output.getvalue())


@mock_retry()
class TestWaitForRoutableState(TestCase):
    @patch(
        "eth_hotplugging._check_routable_state",
        return_value=(True, "routable"),
    )
    def test_reached_routable(self, mock_check_state):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        wait_for_routable_state("eth0", "networkd", do_routable=True)
        sys.stdout = sys.__stdout__
        mock_check_state.assert_called_once_with("eth0", "networkd")
        self.assertIn("Reached routable state", captured_output.getvalue())

    @patch(
        "eth_hotplugging._check_routable_state",
        return_value=(False, "configuring"),
    )
    def test_not_reached_routable(self, mock_check_state):
        with self.assertRaises(SystemExit) as cm:
            wait_for_routable_state("eth0", "networkd", do_routable=True)
        self.assertEqual(str(cm.exception), "Failed to reach routable state!")

    @patch(
        "eth_hotplugging._check_routable_state",
        return_value=(False, ""),
    )
    def test_reached_not_routable(self, mock_check_state):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        wait_for_routable_state("eth0", "networkd", do_routable=False)
        sys.stdout = sys.__stdout__
        self.assertIn("Reached NOT routable state", captured_output.getvalue())

    @patch(
        "eth_hotplugging._check_routable_state",
        return_value=(True, "routable"),
    )
    def test_not_reached_not_routable(self, mock_check_state):
        with self.assertRaises(SystemExit) as cm:
            wait_for_routable_state("eth0", "networkd", do_routable=False)
        self.assertEqual(
            str(cm.exception), "Failed to reach NOT routable state!"
        )


@mock_retry()
class TestWaitForCableState(TestCase):
    @patch("eth_hotplugging.has_cable", return_value=True)
    def test_reached_cable_plugged(self, mock_has_cable):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        wait_for_cable_state("eth0", do_cable=True)
        sys.stdout = sys.__stdout__
        self.assertIn(
            "Detected cable state: plugged", captured_output.getvalue()
        )

    @patch("eth_hotplugging.has_cable", return_value=False)
    def test_not_reached_cable_plugged(self, mock_has_cable):
        with self.assertRaises(SystemExit) as cm:
            wait_for_cable_state("eth0", do_cable=True)
        self.assertEqual(str(cm.exception), "Failed to detect plugged!")

    @patch("eth_hotplugging.has_cable", return_value=False)
    def test_reached_cable_unplugged(self, mock_has_cable):
        captured_output = io.StringIO()
        sys.stdout = captured_output
        wait_for_cable_state("eth0", do_cable=False)
        sys.stdout = sys.__stdout__
        self.assertIn(
            "Detected cable state: unplugged",
            captured_output.getvalue(),
        )

    @patch("eth_hotplugging.has_cable", return_value=True)
    def test_not_reached_cable_unplugged(self, mock_has_cable):
        with self.assertRaises(SystemExit) as cm:
            wait_for_cable_state("eth0", do_cable=False)
        self.assertEqual(str(cm.exception), "Failed to detect unplugged!")


class TestMain(TestCase):
    @patch("eth_hotplugging.perform_ping_test", return_value=0)
    @patch("eth_hotplugging.help_wait_cable_and_routable_state")
    @patch("eth_hotplugging._check_routable_state")
    @patch("eth_hotplugging.has_cable")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["eth_hotplugging.py", "eth0"])
    @patch("builtins.print")
    def test_main_successful_execution(
        self,
        mock_print,
        mock_input,
        mock_has_cable,
        mock_check_routable_state,
        mock_help_wait,
        mock_ping_test,
    ):
        mock_has_cable.return_value = True
        mock_check_routable_state.return_value = (True, "routable")
        main()

    @patch("eth_hotplugging.perform_ping_test", return_value=1)
    @patch("eth_hotplugging.help_wait_cable_and_routable_state")
    @patch("eth_hotplugging._check_routable_state")
    @patch("eth_hotplugging.has_cable")
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["eth_hotplugging.py", "eth0"])
    @patch("builtins.print")
    def test_main_ping_test_failure(
        self,
        mock_print,
        mock_input,
        mock_has_cable,
        mock_check_routable_state,
        mock_help_wait,
        mock_ping_test,
    ):
        mock_has_cable.return_value = True
        mock_check_routable_state.return_value = (True, "routable")
        with self.assertRaises(SystemExit):
            main()

    @patch("sys.argv", ["eth_hotplugging.py"])
    def test_main_no_interface_argument(self):
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception),
            "Usage eth_hotplugging.py INTERFACE_NAME",
        )

    @patch("eth_hotplugging.has_cable", side_effect=FileNotFoundError)
    @patch("builtins.input", return_value="")
    @patch("sys.argv", ["eth_hotplugging.py", "eth0"])
    def test_main_raises_error_when_interface_not_found(
        self, mock_input, mock_has_cable
    ):
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertIn(
            "Could not check the cable for 'eth0'",
            str(cm.exception),
        )


if __name__ == "__main__":
    unittest.main()
