#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2024 Canonical Ltd.
# Written by:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open, ANY
import datetime

from wifi_client_test_netplan import (
    netplan_renderer,
    check_and_get_renderer,
    netplan_config_backup,
    _get_networkctl_state,
    _get_nmcli_state,
    _check_routable_state,
    wait_for_routable,
    get_gateway,
    perform_ping_test,
    generate_test_config,
    parse_args,
    print_journal_entries,
    main,
)


class WifiClientTestNetplanTests(TestCase):
    def test_open_ap_with_dhcp(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              renderer: networkd
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap: {}
                  dhcp4: true
                  nameservers: {}
            """
        )

        result = generate_test_config(
            "eth0", "my_ap", None, "", True, False, "networkd"
        )
        self.assertEqual(result.strip(), expected_output.strip())

    def test_private_ap_with_dhcp(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              renderer: networkd
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap:
                      auth:
                        key-management: psk
                        password: s3cr3t
                  dhcp4: true
                  nameservers: {}
            """
        )
        result = generate_test_config(
            "eth0", "my_ap", "s3cr3t", "", True, False, "networkd"
        )
        self.assertEqual(result.strip(), expected_output.strip())

    def test_private_ap_with_wpa3(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              renderer: networkd
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap_wpa3:
                      auth:
                        key-management: sae
                        password: s3cr3t
                  dhcp4: false
                  nameservers: {}
            """
        )
        result = generate_test_config(
            "eth0", "my_ap_wpa3", "s3cr3t", "", False, True, "networkd"
        )
        self.assertEqual(result.strip(), expected_output.strip())

    def test_static_ip_no_dhcp(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              renderer: networkd
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap:
                      auth:
                        key-management: psk
                        password: s3cr3t
                  addresses:
                  - 192.168.1.1
                  dhcp4: false
                  nameservers: {}
            """
        )
        result = generate_test_config(
            "eth0", "my_ap", "s3cr3t", "192.168.1.1", False, False, "networkd"
        )
        self.assertEqual(result.strip(), expected_output.strip())

    def test_no_ssid_fails(self):
        with self.assertRaises(SystemExit):
            generate_test_config(
                "eth0", "", "s3cr3t", "192.168.1.1", False, False, "networkd"
            )

    @patch("subprocess.call")
    def test_print_journal_entries_networkd(self, mock_call):
        start_time = datetime.datetime(2021, 1, 1, 12, 0)
        print_journal_entries(start_time, "networkd")
        expected_command = (
            "journalctl -q --no-pager -u systemd-networkd.service "
            "-u wpa_supplicant.service "
            '-u netplan-* --since "2021-01-01 12:00:00" '
        )
        mock_call.assert_called_once_with(expected_command, shell=True)

    @patch("subprocess.call")
    def test_print_journal_entries_networkmanager(self, mock_call):
        start_time = datetime.datetime(2021, 1, 1, 12, 0)
        print_journal_entries(start_time, "NetworkManager")
        expected_command = (
            "journalctl -q --no-pager -u NetworkManager.service "
            "-u wpa_supplicant.service "
            '-u netplan-* --since "2021-01-01 12:00:00" '
        )
        mock_call.assert_called_once_with(expected_command, shell=True)

    def test_print_journal_entries_unknown_renderer(self):
        start_time = datetime.datetime(2021, 1, 1, 12, 0)
        with self.assertRaises(ValueError) as context:
            print_journal_entries(start_time, "unknown")
        self.assertTrue("Unknown renderer: unknown" in str(context.exception))

    def test_parser_psk_and_wpa3(self):
        with patch(
            "sys.argv",
            [
                "script.py",
                "-i",
                "eth0",
                "-s",
                "SSID",
                "-k",
                "pswd",
                "-d",
                "--wpa3",
            ],
        ):
            args = parse_args()
            self.assertEqual(args.interface, "eth0")
            self.assertEqual(args.psk, "pswd")
            self.assertTrue(args.wpa3)

    def test_parser_custom_interface_with_address(self):
        with patch(
            "sys.argv",
            ["script.py", "-s", "SSID", "-a", "192.168.1.1/24", "--wpa3"],
        ):
            args = parse_args()
            self.assertEqual(args.address, "192.168.1.1/24")
            self.assertTrue(args.wpa3)
            self.assertFalse(args.dhcp)

    @patch(
        "sys.argv", ["script.py", "-s", "SSID", "-a", "192.168.1.1/24", "-d"]
    )
    def test_parser_mutually_exclusive_fail(self):
        with patch(
            "sys.argv",
            ["script.py", "-s", "SSID", "-a", "192.168.1.1/24", "-d"],
        ):
            with self.assertRaises(SystemExit):
                parse_args()

    @patch(
        "sys.argv",
        [
            "script.py",
            "-i",
            "wlan0",
            "-s",
            "SSID",
            "-d",
            "--renderer",
            "networkd",
        ],
    )
    def test_parser_networkd(self):
        args = parse_args()
        self.assertEqual(args.renderer, "networkd")
        self.assertEqual(args.interface, "wlan0")
        self.assertEqual(args.ssid, "SSID")
        self.assertTrue(args.dhcp)
        self.assertFalse(args.wpa3)
        self.assertIsNone(args.psk)
        self.assertEqual(args.address, "")

    @patch(
        "sys.argv",
        [
            "script.py",
            "-i",
            "wlan0",
            "-s",
            "SSID",
            "-d",
            "--renderer",
            "NetworkManager",
        ],
    )
    def test_parser_networkmanager(self):
        args = parse_args()
        self.assertEqual(args.renderer, "NetworkManager")
        self.assertEqual(args.interface, "wlan0")
        self.assertEqual(args.ssid, "SSID")
        self.assertTrue(args.dhcp)
        self.assertFalse(args.wpa3)
        self.assertIsNone(args.psk)
        self.assertEqual(args.address, "")

    def test_parser_no_renderer(self):
        with patch(
            "sys.argv", ["script.py", "-i", "wlan0", "-s", "SSID", "-d"]
        ):
            args = parse_args()
            self.assertEqual(args.renderer, "AutoDetect")
            self.assertEqual(args.interface, "wlan0")
            self.assertEqual(args.ssid, "SSID")
            self.assertTrue(args.dhcp)
            self.assertFalse(args.wpa3)
            self.assertIsNone(args.psk)
            self.assertEqual(args.address, "")

    def test_parser_autodetect_renderer(self):
        with patch(
            "sys.argv",
            [
                "script.py",
                "-i",
                "wlan0",
                "-s",
                "SSID",
                "-d",
                "--renderer",
                "AutoDetect",
            ],
        ):
            args = parse_args()
            self.assertEqual(args.renderer, "AutoDetect")
            self.assertEqual(args.interface, "wlan0")
            self.assertEqual(args.ssid, "SSID")
            self.assertTrue(args.dhcp)
            self.assertFalse(args.wpa3)
            self.assertIsNone(args.psk)
            self.assertEqual(args.address, "")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="network:\n  renderer: networkd",
    )
    @patch("glob.glob", return_value=["/etc/netplan/01-netcfg.yaml"])
    @patch("os.path.exists", return_value=True)
    def test_renderer_networkd(self, mock_exists, mock_glob, mock_open):
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
        self.assertEqual(renderer, "networkd")

    @patch(
        "wifi_client_test_netplan.netplan_renderer", return_value="networkd"
    )
    def test_auto_detect_matches_networkd(self, mock_renderer):
        self.assertEqual(check_and_get_renderer("AutoDetect"), "networkd")

    @patch(
        "wifi_client_test_netplan.netplan_renderer", return_value="networkd"
    )
    def test_explicit_networkd_matches(self, mock_renderer):
        self.assertEqual(check_and_get_renderer("networkd"), "networkd")

    @patch(
        "wifi_client_test_netplan.netplan_renderer", return_value="networkd"
    )
    def test_explicit_network_manager_mismatch(self, mock_renderer):
        with self.assertRaises(SystemExit):
            check_and_get_renderer("NetworkManager")

    @patch(
        "wifi_client_test_netplan.netplan_renderer",
        return_value="NetworkManager",
    )
    def test_auto_detect_matches_network_manager(self, mock_renderer):
        self.assertEqual(
            check_and_get_renderer("AutoDetect"), "NetworkManager"
        )

    @patch(
        "wifi_client_test_netplan.netplan_renderer",
        return_value="NetworkManager",
    )
    def test_explicit_network_manager_matches(self, mock_renderer):
        self.assertEqual(
            check_and_get_renderer("NetworkManager"), "NetworkManager"
        )

    @patch(
        "wifi_client_test_netplan.netplan_renderer",
        return_value="NetworkManager",
    )
    def test_explicit_networkd_mismatch_with_network_manager(
        self, mock_renderer
    ):
        with self.assertRaises(SystemExit):
            check_and_get_renderer("networkd")

    @patch("shutil.rmtree", side_effect=lambda x: None)
    @patch("shutil.copy")
    @patch(
        "os.path.exists", return_value=True
    )  # Assuming the path always exists
    @patch("glob.glob", return_value=["/etc/netplan/config.yaml"])
    @patch("os.makedirs")
    def test_netplan_config_backup_existing_backup(
        self, mock_makedirs, mock_glob, mock_exists, mock_copy, mock_rmtree
    ):
        netplan_config_backup()
        # Ensure the conditions under which shutil.copy is called only once
        # are met
        mock_copy.assert_called_with("/etc/netplan/config.yaml", ANY)

    @patch("shutil.rmtree", side_effect=lambda x: None)
    @patch("shutil.copy")
    @patch(
        "os.path.exists", return_value=True
    )  # Adjust based on function logic
    @patch("glob.glob", return_value=[])
    @patch("os.makedirs")
    def test_netplan_config_backup_no_config_files(
        self, mock_makedirs, mock_glob, mock_exists, mock_copy, mock_rmtree
    ):
        netplan_config_backup()
        # Assert based on expected behavior when no config files are found
        mock_copy.assert_not_called()

    @patch("shutil.rmtree", side_effect=lambda x: None)
    @patch("shutil.copy")
    @patch(
        "os.path.exists",
        side_effect=lambda x: (
            False if x == "specific_condition_path" else True
        ),
    )
    @patch("glob.glob", return_value=["/etc/netplan/config.yaml"])
    @patch("os.makedirs")
    def test_netplan_config_backup_no_existing_backup(
        self, mock_makedirs, mock_glob, mock_exists, mock_copy, mock_rmtree
    ):
        netplan_config_backup()

    @patch("subprocess.check_output")
    def test_networkd_routable(self, mock_check_output):
        mock_check_output.return_value = b"State: routable"
        routable, state = _check_routable_state("wlan0", "networkd")
        self.assertTrue(routable)
        self.assertIn("routable", state)

    @patch("subprocess.check_output")
    def test_networkd_not_routable(self, mock_check_output):
        mock_check_output.return_value = b"State: degraded"
        routable, state = _check_routable_state("wlan0", "networkd")
        self.assertFalse(routable)
        self.assertIn("degraded", state)

    @patch("subprocess.check_output")
    def test_networkmanager_connected(self, mock_check_output):
        mock_check_output.return_value = b"GENERAL.STATE: 100 (connected)"
        routable, state = _check_routable_state("wlan0", "NetworkManager")
        self.assertTrue(routable)
        self.assertIn("connected", state)

    @patch("subprocess.check_output")
    def test_networkmanager_not_connected(self, mock_check_output):
        mock_check_output.return_value = b"GENERAL.STATE: 30 (disconnected)"
        routable, state = _check_routable_state("wlan0", "NetworkManager")
        self.assertFalse(routable)
        self.assertIn("disconnected", state)

    def test_unknown_renderer(self):
        with self.assertRaises(ValueError):
            _check_routable_state("wlan0", "unknown_renderer")

    @patch("subprocess.check_output")
    def test_get_networkctl_state_success(self, mock_check_output):
        mock_check_output.return_value = (
            b"State: routable\nPath: pci-0000:02:00.0"
        )
        interface = "wlan0"
        state = _get_networkctl_state(interface)
        self.assertEqual(state, " routable", "Should return 'routable' state")

    @patch("subprocess.check_output")
    def test_get_networkctl_state_no_state_line(self, mock_check_output):
        mock_check_output.return_value = (
            b"Some other info: value\nsome more info"
        )
        interface = "wlan0"
        state = _get_networkctl_state(interface)
        self.assertIsNone(
            state, "Should return None when 'State' line is missing"
        )

    @patch("subprocess.check_output")
    def test_get_networkctl_state_empty_output(self, mock_check_output):
        mock_check_output.return_value = b""
        interface = "wlan0"
        state = _get_networkctl_state(interface)
        self.assertIsNone(state, "Should return None for empty command output")

    @patch("subprocess.check_output", side_effect=Exception("Command failed"))
    def test_get_networkctl_state_command_fails(self, mock_check_output):
        interface = "wlan0"
        with self.assertRaises(
            Exception, msg="Should raise an exception for command failure"
        ):
            _get_networkctl_state(interface)

    @patch("subprocess.check_output")
    def test_get_nmcli_state_success(self, mock_check_output):
        mock_check_output.return_value = (
            b"GENERAL.MTU:                            1500\n"
            b"some other info\n"
            b"GENERAL.STATE:                          100 (connected)"
        )
        interface = "wlan0"
        state = _get_nmcli_state(interface)
        self.assertEqual(
            state, "100 (connected)", "Should return '100 (connected)' state"
        )

    @patch("subprocess.check_output")
    def test_get_nmcli_state_unexpected_output(self, mock_check_output):
        mock_check_output.return_value = b"some unexpected output"
        interface = "wlan0"
        state = _get_nmcli_state(interface)
        self.assertIsNone(
            state,
            "Should return None when expected state information is missing",
        )

    @patch("subprocess.check_output", side_effect=Exception("Command failed"))
    def test_get_nmcli_state_command_fails(self, mock_check_output):
        interface = "wlan0"
        with self.assertRaises(
            Exception, msg="Should raise an exception for command failure"
        ):
            _get_nmcli_state(interface)

    @patch("wifi_client_test_netplan._check_routable_state")
    @patch("wifi_client_test_netplan.time.sleep", return_value=None)
    def test_wait_for_routable_networkd(
        self, mock_sleep, mock_check_routable_state
    ):
        mock_check_routable_state.side_effect = [
            (False, ""),
            (False, ""),
            (True, ""),
        ]
        result = wait_for_routable("wlan0", "networkd")
        self.assertTrue(result)
        self.assertEqual(mock_check_routable_state.call_count, 3)
        mock_check_routable_state.assert_called_with("wlan0", "networkd")

    @patch("wifi_client_test_netplan._check_routable_state")
    @patch("wifi_client_test_netplan.time.sleep", return_value=None)
    def test_wait_for_no_routable_networkd(
        self, mock_sleep, mock_check_routable_state
    ):
        mock_check_routable_state.side_effect = [
            (False, ""),
            (False, ""),
            (False, ""),
        ]
        result = wait_for_routable("wlan0", "networkd", 3)
        self.assertFalse(result)
        self.assertEqual(mock_check_routable_state.call_count, 3)
        mock_check_routable_state.assert_called_with("wlan0", "networkd")

    @patch("wifi_client_test_netplan._check_routable_state")
    @patch("wifi_client_test_netplan.time.sleep", return_value=None)
    def test_wait_for_routable_networkmanager(
        self, mock_sleep, mock_check_routable_state
    ):
        mock_check_routable_state.side_effect = [
            (False, ""),
            (True, ""),
        ]
        result = wait_for_routable("wlan0", "NetworkManager", 3)
        self.assertTrue(result)
        self.assertEqual(mock_check_routable_state.call_count, 2)
        mock_check_routable_state.assert_called_with("wlan0", "NetworkManager")

    @patch("wifi_client_test_netplan._check_routable_state")
    @patch("wifi_client_test_netplan.time.sleep", return_value=None)
    def test_wait_for_no_routable_networkmanager(
        self, mock_sleep, mock_check_routable_state
    ):
        mock_check_routable_state.side_effect = [
            (False, ""),
            (False, ""),
            (False, ""),
        ]
        result = wait_for_routable("wlan0", "NetworkManager", 3)
        self.assertFalse(result)
        self.assertEqual(mock_check_routable_state.call_count, 3)
        mock_check_routable_state.assert_called_with("wlan0", "NetworkManager")

    @patch("subprocess.check_output")
    def test_get_gateway_networkd(self, mock_check_output):
        # Setup: Mock the subprocess output for networkd
        mock_check_output.return_value = b"Gateway: 192.168.1.1\n"
        interface = "wlan0"
        renderer = "networkd"

        # Execution: Call the get_gateway function
        gateway = get_gateway(interface, renderer)

        # Verification: Verify the correct gateway is returned
        self.assertEqual(gateway, "192.168.1.1")

    @patch("subprocess.check_output")
    def test_get_gateway_networkd_failure(self, mock_check_output):
        mock_check_output.return_value = b"ABC:123\n abc:zxc\n"
        interface = "wlan0"
        renderer = "networkd"

        gateway = get_gateway(interface, renderer)
        self.assertIsNone(gateway)

    @patch("subprocess.check_output")
    def test_get_gateway_networkmanager(self, mock_check_output):
        mock_check_output.return_value = (
            b"IP4.GATEWAY:                        192.168.1.1\n"
        )
        interface = "wlan0"
        renderer = "NetworkManager"

        gateway = get_gateway(interface, renderer)

        self.assertEqual(gateway, "192.168.1.1")

    @patch("subprocess.check_output")
    def test_get_gateway_networkmanager_failure(self, mock_check_output):
        mock_check_output.return_value = b"ABC:123\n abc:zxc\n"
        interface = "wlan0"
        renderer = "NetworkManager"
        gateway = get_gateway(interface, renderer)
        self.assertIsNone(gateway)

    @patch("subprocess.check_output")
    def test_get_gateway_unknown_renderer(self, mock_check_output):
        interface = "wlan0"
        renderer = "unknown_renderer"
        with self.assertRaises(ValueError):
            get_gateway(interface, renderer)

    @patch("wifi_client_test_netplan.ping")
    @patch("wifi_client_test_netplan.get_gateway")
    def test_perform_ping_test_success_networkd(
        self, mock_get_gateway, mock_ping
    ):
        mock_get_gateway.return_value = "192.168.1.1"
        mock_ping.return_value = {"received": 5}
        result = perform_ping_test("wlan0", "networkd")
        self.assertTrue(result)

    @patch("wifi_client_test_netplan.ping")
    @patch("wifi_client_test_netplan.get_gateway")
    def test_perform_ping_test_failure_networkd(
        self, mock_get_gateway, mock_ping
    ):
        mock_get_gateway.return_value = "192.168.1.1"
        mock_ping.return_value = {"received": 0}
        result = perform_ping_test("wlan0", "networkd")
        self.assertFalse(result)

    @patch("wifi_client_test_netplan.ping")
    @patch("wifi_client_test_netplan.get_gateway")
    def test_perform_ping_test_success_networkmanager(
        self, mock_get_gateway, mock_ping
    ):
        mock_get_gateway.return_value = "192.168.1.1"
        mock_ping.return_value = {"received": 5}
        result = perform_ping_test("wlan0", "NetworkManager")
        self.assertTrue(result)

    @patch("wifi_client_test_netplan.ping")
    @patch("wifi_client_test_netplan.get_gateway")
    def test_perform_ping_test_failure_networkmanager(
        self, mock_get_gateway, mock_ping
    ):
        mock_get_gateway.return_value = "192.168.1.1"
        mock_ping.return_value = {"received": 0}
        result = perform_ping_test("wlan0", "NetworkManager")
        self.assertFalse(result)


class MainTests(TestCase):
    @patch("wifi_client_test_netplan.wait_for_routable", return_value=True)
    @patch("wifi_client_test_netplan.print_address_info")
    @patch("wifi_client_test_netplan.print_route_info")
    @patch("wifi_client_test_netplan.perform_ping_test", return_value=True)
    @patch("wifi_client_test_netplan.delete_test_config")
    @patch("wifi_client_test_netplan.netplan_config_restore")
    @patch("wifi_client_test_netplan.print_journal_entries")
    @patch("wifi_client_test_netplan.time.sleep", return_value=None)
    @patch(
        "wifi_client_test_netplan.parse_args",
        return_value=MagicMock(renderer="NetworkManager"),
    )
    @patch("os.remove")
    def test_main_success(self, *args):
        with self.assertRaises(SystemExit) as cm:
            main()
