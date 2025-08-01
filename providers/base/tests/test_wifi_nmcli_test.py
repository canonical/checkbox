#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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


import subprocess
import unittest
from subprocess import CalledProcessError
from unittest.mock import patch, call, MagicMock
from pathlib import Path
import shutil
import tempfile

from checkbox_support.helpers.retry import mock_retry

from wifi_nmcli_test import (
    legacy_nmcli,
    _get_nm_wireless_connections,
    get_nm_activate_connection,
    turn_up_connection,
    turn_down_nm_connections,
    delete_test_ap_ssid_connection,
    device_rescan,
    list_aps,
    show_aps,
    wait_for_connected,
    connection,
    open_connection,
    secured_connection,
    print_address_info,
    print_route_info,
    perform_ping_test,
    parser_args,
    main,
    restore_netplan_files,
    backup_netplan_files,
)


class WifiNmcliBackupTests(unittest.TestCase):
    @patch("wifi_nmcli_test.sp")
    def test_legacy_nmcli_true(self, subprocess_mock):
        subprocess_mock.check_output.return_value = (
            "nmcli tool, version 1.9.8-5"
        )
        self.assertTrue(legacy_nmcli())

    @patch("wifi_nmcli_test.sp")
    def test_legacy_nmcli_false(self, subprocess_mock):
        subprocess_mock.check_output.return_value = (
            "nmcli tool, version 1.46.0-2"
        )
        self.assertFalse(legacy_nmcli())


class TestGetNmWirelessConnections(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_output", return_value="")
    def test_no_wireless_connections(self, check_output_mock):
        expected = {}
        self.assertEqual(_get_nm_wireless_connections(), expected)

    @patch(
        "wifi_nmcli_test.sp.check_output",
        return_value=(
            "802-11-wireless:uuid1:Wireless1:activated\n"
            "802-3-ethernet:uuid2:Ethernet1:activated\n"
            "802-11-wireless:uuid3:Wireless2:deactivated\n"
        ),
    )
    def test_multiple_wireless_connections(self, check_output_mock):
        expected = {
            "Wireless1": {"uuid": "uuid1", "state": "activated"},
            "Wireless2": {"uuid": "uuid3", "state": "deactivated"},
        }
        self.assertEqual(_get_nm_wireless_connections(), expected)


class TestGetNmActivateConnection(unittest.TestCase):
    @patch("wifi_nmcli_test._get_nm_wireless_connections", return_value={})
    def test_no_active_connections(self, _):
        self.assertEqual(get_nm_activate_connection(), "")

    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={"Wireless1": {"uuid": "uuid1", "state": "activated"}},
    )
    def test_single_active_connection(self, _):
        self.assertEqual(get_nm_activate_connection(), "uuid1")

    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={
            "Wireless1": {"uuid": "uuid1", "state": "deactivated"},
            "Wireless2": {"uuid": "uuid2", "state": "activated"},
            "Wireless3": {"uuid": "uuid3", "state": "deactivated"},
        },
    )
    def test_multiple_connections_one_active(self, _):
        self.assertEqual(get_nm_activate_connection(), "uuid2")


class TestTurnUpConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test.get_nm_activate_connection", return_value="uuid1")
    def test_connection_already_activated(
        self, get_nm_activate_connection_mock, sp_call_mock
    ):
        turn_up_connection("uuid1")
        sp_call_mock.assert_not_called()

    @patch("wifi_nmcli_test.sp.call", return_value=0)
    @patch("wifi_nmcli_test.get_nm_activate_connection", return_value="")
    def test_connection_activation_succeeds(
        self, get_nm_activate_connection_mock, sp_call_mock
    ):
        turn_up_connection("uuid2")
        sp_call_mock.assert_called_with("nmcli c up uuid2".split())

    @patch("wifi_nmcli_test.sp.call", side_effect=Exception("Command failed"))
    @patch("wifi_nmcli_test.get_nm_activate_connection", return_value="")
    def test_connection_activation_fails_due_to_exception(
        self,
        get_nm_activate_connection_mock,
        sp_call_mock,
    ):
        turn_up_connection("uuid3")


class TestTurnDownNmConnections(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test._get_nm_wireless_connections", return_value={})
    def test_no_connections_to_turn_down(
        self, get_connections_mock, sp_call_mock
    ):
        turn_down_nm_connections()
        self.assertEqual(get_connections_mock.call_count, 1)
        sp_call_mock.assert_not_called()

    @patch("wifi_nmcli_test.sp.check_call")
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={"Wireless1": {"uuid": "uuid1", "state": "activated"}},
    )
    def test_turn_down_single_connection(
        self, get_connections_mock, sp_check_call_mock
    ):
        turn_down_nm_connections()
        self.assertEqual(get_connections_mock.call_count, 1)
        sp_check_call_mock.assert_called_once_with(
            "nmcli c down uuid1".split()
        )

    @patch("wifi_nmcli_test.sp.check_call")
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={"Wireless1": {"uuid": "uuid1", "state": "activated"}},
    )
    def test_turn_down_single_connection_with_exception(
        self, get_connections_mock, sp_check_call_mock
    ):
        sp_check_call_mock.side_effect = subprocess.CalledProcessError("", 1)
        with self.assertRaises(subprocess.CalledProcessError):
            turn_down_nm_connections()
        self.assertEqual(get_connections_mock.call_count, 1)
        sp_check_call_mock.assert_called_once_with(
            "nmcli c down uuid1".split()
        )

    @patch("wifi_nmcli_test.sp.check_call")
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={
            "Wireless1": {"uuid": "uuid1", "state": "activated"},
            "Wireless2": {"uuid": "uuid2", "state": "activated"},
        },
    )
    def test_turn_down_multiple_connections(
        self, get_connections_mock, sp_check_call_mock
    ):
        turn_down_nm_connections()
        self.assertEqual(get_connections_mock.call_count, 1)
        calls = [
            call("nmcli c down uuid1".split()),
            call("nmcli c down uuid2".split()),
        ]
        sp_check_call_mock.assert_has_calls(calls, any_order=True)


class TestDeleteTestApSsidConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_call")
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={
            "TEST_CON": {"uuid": "uuid-test", "state": "deactivated"}
        },
    )
    @patch("wifi_nmcli_test.print")
    def test_delete_existing_test_con(
        self, print_mock, get_nm_wireless_connections_mock, sp_check_call_mock
    ):
        delete_test_ap_ssid_connection()
        print_mock.assert_called_with("TEST_CON is deleted")

    @patch("wifi_nmcli_test._get_nm_wireless_connections", return_value={})
    @patch("wifi_nmcli_test.print")
    def test_no_test_con_to_delete(
        self, print_mock, get_nm_wireless_connections_mock
    ):
        delete_test_ap_ssid_connection()
        print_mock.assert_called_with(
            "No TEST_CON connection found, nothing to delete"
        )


class TestListAps(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_output")
    def test_list_aps_no_essid(self, check_output_mock):
        check_output_mock.return_value = (
            "wlan0 \nSSID1:1:2412:60\nSSID2:6:2437:70\nSSID3:11:2462:80"
        )
        expected = {
            "SSID1": {"Chan": "1", "Freq": "2412", "Signal": "60"},
            "SSID2": {"Chan": "6", "Freq": "2437", "Signal": "70"},
            "SSID3": {"Chan": "11", "Freq": "2462", "Signal": "80"},
        }
        self.assertEqual(list_aps("wlan0"), expected)

    @patch("wifi_nmcli_test.sp.check_output")
    def test_list_aps_with_essid(self, check_output_mock):
        check_output_mock.return_value = (
            "SSID1:1:2412:60\nSSID2:6:2437:70\nSSID3:11:2462:80"
        )
        expected = {
            "SSID2": {"Chan": "6", "Freq": "2437", "Signal": "70"},
        }
        self.assertEqual(list_aps("wlan0", "SSID2"), expected)

    @patch("wifi_nmcli_test.sp.check_output")
    def test_list_aps_empty_output(self, check_output_mock):
        check_output_mock.return_value = ""
        expected = {}
        self.assertEqual(list_aps("wlan0"), expected)


class TestShowAps(unittest.TestCase):
    @patch("wifi_nmcli_test.print")
    def test_show_aps_empty(self, mock_print):
        aps_dict = {}
        show_aps(aps_dict)
        mock_print.assert_called_with()

    @patch("wifi_nmcli_test.print")
    def test_show_aps_multiple_aps(self, mock_print):
        aps_dict = {
            "AP1": {"Chan": "1", "Freq": "2412", "Signal": "-40"},
            "AP2": {"Chan": "6", "Freq": "2437", "Signal": "-50"},
        }
        show_aps(aps_dict)
        expected_calls = [
            call("SSID: AP1 Chan: 1 Freq: 2412 Signal: -40"),
            call("SSID: AP2 Chan: 6 Freq: 2437 Signal: -50"),
        ]
        mock_print.assert_has_calls(expected_calls, any_order=True)


@mock_retry()
class TestWaitForConnected(unittest.TestCase):
    @patch("wifi_nmcli_test.print_cmd", new=MagicMock())
    @patch(
        "wifi_nmcli_test.sp.check_output",
        MagicMock(
            side_effect=[
                "100:connected\nTestESSID\n",
            ]
        ),
    )
    def test_wait_for_connected_success(self):
        interface = "wlan0"
        essid = "TestESSID"
        wait_for_connected(interface, essid)

    @patch(
        "wifi_nmcli_test.sp.check_output",
        MagicMock(return_value="30:disconnected\nTestESSID\n"),
    )
    @patch("wifi_nmcli_test.print_cmd", new=MagicMock())
    def test_wait_for_connected_failure_due_to_timeout(self):
        interface = "wlan0"
        essid = "TestESSID"
        with self.assertRaises(SystemExit):
            wait_for_connected(interface, essid)

    @patch(
        "wifi_nmcli_test.sp.check_output",
        MagicMock(return_value="100:connected\nWrongESSID\n"),
    )
    @patch("wifi_nmcli_test.print_cmd", new=MagicMock())
    def test_wait_for_connected_failure_due_to_essid_mismatch(self):
        interface = "wlan0"
        essid = "TestESSID"
        with self.assertRaises(SystemExit):
            wait_for_connected(interface, essid)


class TestConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_call", new=MagicMock())
    @patch("wifi_nmcli_test.print_route_info", new=MagicMock())
    @patch("wifi_nmcli_test.print_address_info", new=MagicMock())
    @patch("wifi_nmcli_test.turn_up_connection", new=MagicMock())
    @patch("wifi_nmcli_test.sp.check_output", new=MagicMock())
    @patch("wifi_nmcli_test.wait_for_connected", return_value=True)
    @patch("wifi_nmcli_test.perform_ping_test", return_value=True)
    def test_connection_success(
        self,
        perform_ping_test_mock,
        wait_for_connected_mock,
    ):
        cmd = "test"
        device = "wlan0"
        connection(cmd, device)
        wait_for_connected_mock.assert_called_with("wlan0", "TEST_CON")
        perform_ping_test_mock.assert_called_with("wlan0")

    @patch("wifi_nmcli_test.sp.check_call", new=MagicMock())
    @patch("wifi_nmcli_test.print_route_info", new=MagicMock())
    @patch("wifi_nmcli_test.print_address_info", new=MagicMock())
    @patch("wifi_nmcli_test.turn_up_connection", new=MagicMock())
    @patch("wifi_nmcli_test.sp.check_output", new=MagicMock())
    @patch("wifi_nmcli_test.wait_for_connected")
    @patch("wifi_nmcli_test.perform_ping_test", return_value=False)
    def test_connection_fail_to_connect(
        self,
        perform_ping_test_mock,
        wait_for_connected_mock,
    ):
        wait_for_connected_mock.side_effect = SystemExit()
        cmd = "test"
        device = "wlan0"
        with self.assertRaises(SystemExit):
            connection(cmd, device)
        wait_for_connected_mock.assert_called_with("wlan0", "TEST_CON")
        perform_ping_test_mock.assert_not_called()

    @patch("wifi_nmcli_test.sp.run")
    @patch("wifi_nmcli_test.print_route_info", new=MagicMock())
    @patch("wifi_nmcli_test.print_address_info", new=MagicMock())
    @patch("wifi_nmcli_test.turn_up_connection", new=MagicMock())
    @patch("wifi_nmcli_test.sp.check_output", new=MagicMock())
    @patch("wifi_nmcli_test.wait_for_connected", return_value=False)
    @patch("wifi_nmcli_test.perform_ping_test", return_value=True)
    def test_connection_command_failure(
        self,
        perform_ping_test_mock,
        wait_for_connected_mock,
        sp_run_mock,
    ):
        sp_run_mock.side_effect = subprocess.CalledProcessError("", 1)
        cmd = "test"
        device = "wlan0"
        with self.assertRaises(subprocess.CalledProcessError):
            connection(cmd, device)
        wait_for_connected_mock.assert_not_called()
        perform_ping_test_mock.assert_not_called()


class TestOpenConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.connection")
    def test_open_connection(self, mock_connection):
        """
        Check that security-related parameters are absent in the command
        sent to connection().
        """
        args = MagicMock()
        args.device = "wlan0"
        args.essid = "TestSSID"
        args.exchange = "wpa-psk"
        args.psk = "password123"
        open_connection(args)
        self.assertNotIn("wifi-sec", mock_connection.call_args[0][0])


class TestSecuredConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.connection")
    def test_secured_connection(self, mock_connection):
        """
        Check that security-related parameters are present in the command
        sent to connection().
        """
        args = MagicMock()
        args.device = "wlan0"
        args.essid = "TestSSID"
        args.exchange = "wpa-psk"
        args.psk = "password123"
        secured_connection(args)
        self.assertIn("wifi-sec", mock_connection.call_args[0][0])


class TestDeviceRescan(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_output")
    def test_device_rescan_success(self, mock_sp_check_call):
        device_rescan()

    @patch("wifi_nmcli_test.sp.check_output")
    def test_device_rescan_success_ok_failure_immediate(
        self, mock_sp_check_call
    ):
        mock_sp_check_call.side_effect = CalledProcessError(
            1,
            cmd="",
            output="Error: Scanning not allowed immediately following previous scan",
        )
        device_rescan()

    @patch("wifi_nmcli_test.sp.check_output")
    def test_device_rescan_success_ok_failure_already(
        self, mock_sp_check_call
    ):
        mock_sp_check_call.side_effect = CalledProcessError(
            1,
            cmd="",
            output="Error: Scanning not allowed while already scanning",
        )
        device_rescan()

    @patch("wifi_nmcli_test.sp.check_output")
    @mock_retry()
    def test_device_rescan_failure(self, mock_sp_check_call):
        mock_sp_check_call.side_effect = CalledProcessError(
            1,
            cmd="",
            output="Error: Very serious error we can't ignore",
        )
        with self.assertRaises(CalledProcessError):
            device_rescan()


class TestPrintAddressInfo(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.call")
    def test_print_address_info_success(self, mock_sp_call):
        print_address_info("wlan0")


class TestPrintRouteInfo(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.call")
    def test_print_route_info_success(self, mock_sp_call):
        print_route_info()


@patch("wifi_nmcli_test.ping")
@patch("wifi_nmcli_test.sp.check_output")
class TestPerformPingTest(unittest.TestCase):
    def test_perform_ping_test_success(self, mock_check_output, mock_ping):
        mock_ping.return_value = {
            "transmitted": 5,
            "received": 5,
            "pct_loss": 0,
        }
        perform_ping_test("wlan0")

    def test_perform_ping_test_failure(self, mock_check_output, mock_ping):
        mock_ping.return_value = {
            "transmitted": 5,
            "received": 0,
            "pct_loss": 0,
        }
        with self.assertRaises(ValueError):
            perform_ping_test("wlan0")


class TestParserArgs(unittest.TestCase):
    @patch("sys.argv", ["wifi_nmcli_test.py", "scan", "wlan0"])
    def test_parser_args_scan(self):
        args = parser_args()
        self.assertEqual(args.test_type, "scan")
        self.assertEqual(args.device, "wlan0")

    @patch("sys.argv", ["wifi_nmcli_test.py", "open", "wlan0", "TestSSID"])
    def test_parser_args_open(self):
        args = parser_args()
        self.assertEqual(args.test_type, "open")
        self.assertEqual(args.device, "wlan0")
        self.assertEqual(args.essid, "TestSSID")

    @patch(
        "sys.argv",
        ["wifi_nmcli_test.py", "secured", "wlan0", "TestSSID", "TestPSK"],
    )
    def test_parser_args_secured(self):
        args = parser_args()
        self.assertEqual(args.test_type, "secured")
        self.assertEqual(args.device, "wlan0")
        self.assertEqual(args.essid, "TestSSID")
        self.assertEqual(args.psk, "TestPSK")
        self.assertEqual(args.exchange, "wpa-psk")

    @patch(
        "sys.argv",
        [
            "wifi_nmcli_test.py",
            "secured",
            "wlan0",
            "TestSSID",
            "TestPSK",
            "--exchange",
            "wpa2-psk",
        ],
    )
    def test_parser_args_secured_with_exchange(self):
        args = parser_args()
        self.assertEqual(args.exchange, "wpa2-psk")

    @patch("sys.argv", ["wifi_nmcli_test.py", "ap", "wlan0", "5GHz"])
    def test_parser_args_ap(self):
        args = parser_args()
        self.assertEqual(args.test_type, "ap")
        self.assertEqual(args.device, "wlan0")
        self.assertEqual(args.band, "5GHz")


@mock_retry()
class TestMainFunction(unittest.TestCase):

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection", new=MagicMock())
    @patch("wifi_nmcli_test.turn_down_nm_connections", new=MagicMock())
    @patch("wifi_nmcli_test.turn_up_connection", new=MagicMock())
    @patch("wifi_nmcli_test.device_rescan", new=MagicMock())
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection", return_value="uuid123"
    )
    @patch("wifi_nmcli_test.list_aps", return_value={})
    @patch("wifi_nmcli_test.sys.argv", ["wifi_nmcli_test.py", "scan", "wlan0"])
    def test_main_scan_no_aps_found(
        self,
        list_aps_mock,
        get_nm_activate_connection_mock,
    ):
        with self.assertRaises(SystemExit):
            main()

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection", new=MagicMock())
    @patch("wifi_nmcli_test.turn_down_nm_connections", new=MagicMock())
    @patch("wifi_nmcli_test.turn_up_connection", new=MagicMock())
    @patch("wifi_nmcli_test.device_rescan", new=MagicMock())
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection",
        return_value="uuid123",
    )
    @patch(
        "wifi_nmcli_test.list_aps",
        return_value={
            "SSID1": {"Chan": "1", "Freq": "2412", "Signal": "60"},
            "SSID2": {"Chan": "6", "Freq": "2437", "Signal": "70"},
            "SSID3": {"Chan": "11", "Freq": "2462", "Signal": "80"},
        },
    )
    @patch("wifi_nmcli_test.sys.argv", ["wifi_nmcli_test.py", "scan", "wlan0"])
    def test_main_scan_aps_found(
        self,
        list_aps_mock,
        get_nm_activate_connection_mock,
    ):
        main()

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection", new=MagicMock())
    @patch("wifi_nmcli_test.turn_down_nm_connections", new=MagicMock())
    @patch("wifi_nmcli_test.turn_up_connection", new=MagicMock())
    @patch("wifi_nmcli_test.device_rescan", new=MagicMock())
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection",
        return_value="uuid123",
    )
    @patch("wifi_nmcli_test.list_aps", return_value={})
    @patch(
        "wifi_nmcli_test.sys.argv",
        ["wifi_nmcli_test.py", "open", "wlan0", "TestSSID"],
    )
    def test_main_open_no_aps_found(
        self,
        list_aps_mock,
        get_nm_activate_connection_mock,
    ):
        with self.assertRaises(SystemExit):
            main()

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection", new=MagicMock())
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection",
        return_value="uuid123",
    )
    @patch("wifi_nmcli_test.turn_down_nm_connections", new=MagicMock())
    @patch("wifi_nmcli_test.turn_up_connection", new=MagicMock())
    @patch("wifi_nmcli_test.device_rescan", new=MagicMock())
    @patch(
        "wifi_nmcli_test.list_aps",
        return_value={
            "SSID1": {"Chan": "1", "Freq": "2412", "Signal": "60"},
            "SSID2": {"Chan": "6", "Freq": "2437", "Signal": "70"},
            "TestSSID": {"Chan": "11", "Freq": "2462", "Signal": "80"},
        },
    )
    @patch("wifi_nmcli_test.backup_netplan_files")
    @patch("wifi_nmcli_test.restore_netplan_files")
    @patch("wifi_nmcli_test.open_connection", return_value=0)
    @patch(
        "wifi_nmcli_test.sys.argv",
        ["wifi_nmcli_test.py", "open", "wlan0", "TestSSID"],
    )
    def test_main_open_aps_found(
        self,
        list_aps_mock,
        get_nm_activate_connection_mock,
        mock_open_connection,
        mock_rest_back,
        mock_cr_back,
    ):
        main()


class TestNetplanBackupFunctions(unittest.TestCase):
    def setUp(self):
        self.TEST_BACKUP_DIR = tempfile.TemporaryDirectory()
        self.TEST_NETPLAN_DIR = tempfile.TemporaryDirectory()

    @patch("glob.glob")
    @patch("builtins.print")
    def test_backup_netplan_files_no_files_found(self, mock_print, mock_glob):
        """Test backup when no YAML files are found."""
        mock_glob.return_value = []

        backup_netplan_files(
            str(self.TEST_BACKUP_DIR.name), str(self.TEST_NETPLAN_DIR.name)
        )

    @patch("os.chown")
    @patch("os.stat")
    @patch("glob.glob")
    @patch("shutil.copy2")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.print")
    def test_backup_netplan_files_success(
        self,
        mock_print,
        mock_mkdir,
        mock_copy2,
        mock_glob,
        mock_stat,
        mock_chown,
    ):
        """Test successful backup of netplan files."""
        mock_glob.return_value = [
            str(self.TEST_NETPLAN_DIR.name) + "/config1.yaml",
            str(self.TEST_NETPLAN_DIR.name) + "/config2.yaml",
        ]

        backup_netplan_files(
            str(self.TEST_BACKUP_DIR.name), str(self.TEST_NETPLAN_DIR.name)
        )

        self.assertEqual(mock_copy2.call_count, 2)
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("os.chown")
    @patch("os.stat")
    @patch("os.path.exists")
    @patch("glob.glob")
    @patch("os.remove")
    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("builtins.print")
    def test_restore_netplan_files_success(
        self,
        mock_print,
        mock_copy2,
        mock_makedirs,
        mock_remove,
        mock_glob,
        mock_exists,
        mock_stat,
        mock_chown,
    ):
        """Test successful restore of netplan files."""
        mock_exists.return_value = True

        mock_glob.side_effect = [
            [],
            [],
        ]

        restore_netplan_files(None, str(self.TEST_NETPLAN_DIR.name))
        restore_netplan_files(
            str(self.TEST_BACKUP_DIR.name), str(self.TEST_NETPLAN_DIR.name)
        )

        mock_glob.side_effect = [
            # Existing files to remove
            [str(self.TEST_NETPLAN_DIR.name) + "/old1.yaml"],
            [
                "{}/config1.yaml".format(str(self.TEST_BACKUP_DIR.name)),
                "{}/config2.yaml".format(str(self.TEST_BACKUP_DIR.name)),
            ],  # Backup files
        ]

        restore_netplan_files(
            str(self.TEST_BACKUP_DIR.name), str(self.TEST_NETPLAN_DIR.name)
        )

        mock_remove.assert_called_once_with(
            str(self.TEST_NETPLAN_DIR.name) + "/old1.yaml"
        )
        self.assertEqual(mock_copy2.call_count, 2)

    @patch("os.path.exists")
    @patch("glob.glob")
    @patch("os.remove")
    @patch("builtins.print")
    def test_restore_netplan_files_remove_error(
        self, mock_print, mock_remove, mock_glob, mock_exists
    ):
        """Test restore when removing existing files fails."""
        mock_exists.return_value = True
        mock_glob.side_effect = [
            # Existing files to remove
            [str(self.TEST_NETPLAN_DIR.name) + "/old1.yaml"],
            # Backup files
            ["{}/config1.yaml".format(str(self.TEST_BACKUP_DIR.name))],
        ]
        mock_remove.side_effect = OSError("Permission denied")
        with self.assertRaises(OSError):
            restore_netplan_files(
                str(self.TEST_BACKUP_DIR.name), str(self.TEST_NETPLAN_DIR.name)
            )

    @patch("os.path.exists")
    @patch("glob.glob")
    @patch("os.makedirs")
    @patch("builtins.print")
    def test_restore_netplan_files_makedirs_error(
        self, mock_print, mock_makedirs, mock_glob, mock_exists
    ):
        """Test restore when makedirs operation fails."""
        mock_exists.return_value = True
        mock_glob.side_effect = [
            [],
            ["{}/config1.yaml".format(str(self.TEST_BACKUP_DIR.name))],
        ]
        mock_makedirs.side_effect = OSError("Permission denied")

        with self.assertRaises(FileNotFoundError):
            restore_netplan_files(
                str(self.TEST_BACKUP_DIR.name), str(self.TEST_NETPLAN_DIR.name)
            )
