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


import unittest
from unittest.mock import patch, call, MagicMock
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
    open_connection,
    secured_connection,
    hotspot,
    parser_args,
    main,
)


class WifiNmcliBackupTests(unittest.TestCase):
    @patch("wifi_nmcli_test.sp")
    def test_legacy_nmcli_true(self, subprocess_mock):
        subprocess_mock.check_output.return_value = (
            b"nmcli tool, version 1.9.8-5"
        )
        self.assertTrue(legacy_nmcli())

    @patch("wifi_nmcli_test.sp")
    def test_legacy_nmcli_false(self, subprocess_mock):
        subprocess_mock.check_output.return_value = (
            b"nmcli tool, version 1.46.0-2"
        )
        self.assertFalse(legacy_nmcli())


class TestGetNmWirelessConnections(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_output", return_value=b"")
    def test_no_wireless_connections(self, check_output_mock):
        expected = {}
        self.assertEqual(_get_nm_wireless_connections(), expected)

    @patch(
        "wifi_nmcli_test.sp.check_output",
        return_value=(
            b"802-11-wireless:uuid1:Wireless1:activated\n"
            b"802-3-ethernet:uuid2:Ethernet1:activated\n"
            b"802-11-wireless:uuid3:Wireless2:deactivated\n"
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

    @patch("wifi_nmcli_test.sp.call")
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={"Wireless1": {"uuid": "uuid1", "state": "activated"}},
    )
    def test_turn_down_single_connection(
        self, get_connections_mock, sp_call_mock
    ):
        turn_down_nm_connections()
        self.assertEqual(get_connections_mock.call_count, 1)
        sp_call_mock.assert_called_once_with("nmcli c down uuid1".split())

    @patch(
        "wifi_nmcli_test.sp.call", side_effect=Exception("Error turning down")
    )
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={"Wireless1": {"uuid": "uuid1", "state": "activated"}},
    )
    def test_turn_down_single_connection_with_exception(
        self, get_connections_mock, sp_call_mock
    ):
        turn_down_nm_connections()
        self.assertEqual(get_connections_mock.call_count, 1)
        sp_call_mock.assert_called_once_with("nmcli c down uuid1".split())

    @patch("wifi_nmcli_test.sp.call")
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={
            "Wireless1": {"uuid": "uuid1", "state": "activated"},
            "Wireless2": {"uuid": "uuid2", "state": "activated"},
        },
    )
    def test_turn_down_multiple_connections(
        self, get_connections_mock, sp_call_mock
    ):
        turn_down_nm_connections()
        self.assertEqual(get_connections_mock.call_count, 1)
        calls = [
            call("nmcli c down uuid1".split()),
            call("nmcli c down uuid2".split()),
        ]
        sp_call_mock.assert_has_calls(calls, any_order=True)


class TestDeleteTestApSsidConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.call", return_value=0)
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={
            "TEST_CON": {"uuid": "uuid-test", "state": "deactivated"}
        },
    )
    @patch("wifi_nmcli_test.print")
    def test_delete_existing_test_con(
        self, get_nm_wireless_connections_mock, sp_call_mock, print_mock
    ):
        delete_test_ap_ssid_connection()

    @patch("wifi_nmcli_test.sp.call", side_effect=Exception("Deletion failed"))
    @patch(
        "wifi_nmcli_test._get_nm_wireless_connections",
        return_value={
            "TEST_CON": {"uuid": "uuid-test", "state": "deactivated"}
        },
    )
    def test_delete_test_con_exception(
        self, get_nm_wireless_connections_mock, sp_call_mock
    ):
        delete_test_ap_ssid_connection()

    @patch("wifi_nmcli_test._get_nm_wireless_connections", return_value={})
    def test_no_test_con_to_delete(self, get_nm_wireless_connections_mock):
        delete_test_ap_ssid_connection()


class TestListAps(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_output")
    def test_list_aps_no_essid(self, check_output_mock):
        check_output_mock.return_value = (
            b"wlan0 \nSSID1:1:2412:60\nSSID2:6:2437:70\nSSID3:11:2462:80"
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
            b"SSID1:1:2412:60\nSSID2:6:2437:70\nSSID3:11:2462:80"
        )
        expected = {
            "SSID2": {"Chan": "6", "Freq": "2437", "Signal": "70"},
        }
        self.assertEqual(list_aps("wlan0", "SSID2"), expected)

    @patch("wifi_nmcli_test.sp.check_output")
    def test_list_aps_empty_output(self, check_output_mock):
        check_output_mock.return_value = b""
        expected = {}
        self.assertEqual(list_aps("wlan0"), expected)


class TestShowAps(unittest.TestCase):
    @patch("wifi_nmcli_test.print")
    def test_show_aps_empty(self, mock_print):
        aps_dict = {}
        show_aps(aps_dict)

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


class TestWaitForConnected(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.check_output")
    @patch("wifi_nmcli_test.print_cmd")
    @patch("wifi_nmcli_test.time.sleep", return_value=None)
    def test_wait_for_connected_success(
        self, mock_sleep, mock_print_cmd, mock_check_output
    ):
        mock_check_output.side_effect = [
            b"100:connected\nTestESSID",
        ]
        interface = "wlan0"
        essid = "TestESSID"
        self.assertTrue(wait_for_connected(interface, essid))

    @patch(
        "wifi_nmcli_test.sp.check_output",
        return_value=b"30:disconnected\nTestESSID",
    )
    @patch("wifi_nmcli_test.print_cmd")
    @patch("wifi_nmcli_test.time.sleep", return_value=None)
    def test_wait_for_connected_failure_due_to_timeout(
        self, mock_sleep, mock_print_cmd, mock_check_output
    ):
        interface = "wlan0"
        essid = "TestESSID"
        self.assertFalse(wait_for_connected(interface, essid, max_wait=3))

    @patch(
        "wifi_nmcli_test.sp.check_output",
        return_value=b"100:connected\nWrongESSID",
    )
    @patch("wifi_nmcli_test.print_cmd")
    @patch("wifi_nmcli_test.time.sleep", return_value=None)
    def test_wait_for_connected_failure_due_to_essid_mismatch(
        self, mock_sleep, mock_print_cmd, mock_check_output
    ):
        interface = "wlan0"
        essid = "TestESSID"
        self.assertFalse(wait_for_connected(interface, essid))


class TestOpenConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test.perform_ping_test", return_value=True)
    @patch("wifi_nmcli_test.wait_for_connected", return_value=True)
    @patch("wifi_nmcli_test.print_address_info")
    @patch("wifi_nmcli_test.print_route_info")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch("wifi_nmcli_test.print_head")
    @patch("wifi_nmcli_test.print_cmd")
    def test_open_connection_success(
        self,
        print_cmd_mock,
        print_head_mock,
        turn_up_mock,
        print_route_info_mock,
        print_address_info_mock,
        wait_for_connected_mock,
        perform_ping_test_mock,
        sp_call_mock,
    ):
        args = type("", (), {})()
        args.device = "wlan0"
        args.essid = "TestESSID"
        rc = open_connection(args)
        self.assertEqual(rc, 0)

    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test.perform_ping_test", return_value=False)
    @patch("wifi_nmcli_test.wait_for_connected", return_value=True)
    @patch("wifi_nmcli_test.print_address_info")
    @patch("wifi_nmcli_test.print_route_info")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch("wifi_nmcli_test.print_head")
    @patch("wifi_nmcli_test.print_cmd")
    def test_open_connection_failed_ping(
        self,
        print_cmd_mock,
        print_head_mock,
        turn_up_mock,
        print_route_info_mock,
        print_address_info_mock,
        wait_for_connected_mock,
        perform_ping_test_mock,
        sp_call_mock,
    ):
        args = type("", (), {})()
        args.device = "wlan0"
        args.essid = "TestESSID"
        rc = open_connection(args)
        self.assertEqual(rc, 1)

    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test.wait_for_connected", return_value=False)
    @patch("wifi_nmcli_test.print_head")
    @patch("wifi_nmcli_test.print_cmd")
    @patch("wifi_nmcli_test.turn_up_connection")
    def test_open_connection_failed_to_connect(
        self,
        print_cmd_mock,
        turn_up_mock,
        print_head_mock,
        wait_for_connected_mock,
        sp_call_mock,
    ):
        args = type("", (), {})()
        args.device = "wlan0"
        args.essid = "TestESSID"
        rc = open_connection(args)
        self.assertEqual(rc, 1)


class TestSecuredConnection(unittest.TestCase):
    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test.wait_for_connected", return_value=True)
    @patch("wifi_nmcli_test.perform_ping_test", return_value=True)
    @patch("wifi_nmcli_test.print_route_info")
    @patch("wifi_nmcli_test.print_address_info")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch("wifi_nmcli_test.sp.check_output")
    def test_secured_connection_success(
        self,
        check_output_mock,
        turn_up_connection_mock,
        print_address_info_mock,
        print_route_info_mock,
        perform_ping_test_mock,
        wait_for_connected_mock,
        sp_call_mock,
    ):
        args = type("", (), {})()
        args.device = "wlan0"
        args.essid = "TestSSID"
        args.exchange = "wpa-psk"
        args.psk = "password123"
        rc = secured_connection(args)
        self.assertEqual(rc, 0)
        wait_for_connected_mock.assert_called_with("wlan0", "TestSSID")
        perform_ping_test_mock.assert_called_with("wlan0")

    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test.wait_for_connected", return_value=False)
    @patch("wifi_nmcli_test.perform_ping_test", return_value=False)
    @patch("wifi_nmcli_test.print_route_info")
    @patch("wifi_nmcli_test.print_address_info")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch("wifi_nmcli_test.sp.check_output")
    def test_secured_connection_fail_to_connect(
        self,
        check_output_mock,
        turn_up_connection_mock,
        print_address_info_mock,
        print_route_info_mock,
        perform_ping_test_mock,
        wait_for_connected_mock,
        sp_call_mock,
    ):
        args = type("", (), {})()
        args.device = "wlan0"
        args.essid = "TestSSID"
        args.exchange = "wpa-psk"
        args.psk = "password123"
        rc = secured_connection(args)
        self.assertEqual(rc, 1)
        wait_for_connected_mock.assert_called_with("wlan0", "TestSSID")
        perform_ping_test_mock.assert_not_called()

    @patch("wifi_nmcli_test.sp.call")
    @patch("wifi_nmcli_test.wait_for_connected", return_value=False)
    @patch("wifi_nmcli_test.perform_ping_test", return_value=True)
    @patch("wifi_nmcli_test.print_route_info")
    @patch("wifi_nmcli_test.print_address_info")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch("wifi_nmcli_test.sp.check_output")
    def test_secured_connection_command_failure(
        self,
        check_output_mock,
        turn_up_connection_mock,
        print_address_info_mock,
        print_route_info_mock,
        perform_ping_test_mock,
        wait_for_connected_mock,
        sp_call_mock,
    ):
        args = type("", (), {})()
        args.device = "wlan0"
        args.essid = "TestSSID"
        args.exchange = "wpa-psk"
        args.psk = "password123"
        rc = secured_connection(args)
        self.assertEqual(rc, 1)
        wait_for_connected_mock.assert_called_with("wlan0", "TestSSID")
        perform_ping_test_mock.assert_not_called()


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


class TestMainFunction(unittest.TestCase):

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection")
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection", return_value="uuid123"
    )
    @patch("wifi_nmcli_test.turn_down_nm_connections")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch("wifi_nmcli_test.list_aps", return_value={})
    @patch("wifi_nmcli_test.sys.argv", ["wifi_nmcli_test.py", "scan", "wlan0"])
    @patch("wifi_nmcli_test.device_rescan")
    def test_main_scan_no_aps_found(
        self,
        list_aps_mock,
        turn_up_connection_mock,
        turn_down_nm_connections_mock,
        get_nm_activate_connection_mock,
        delete_test_ap_ssid_connection_mock,
        mock_device_rescan,
    ):
        main()

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection")
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection", return_value="uuid123"
    )
    @patch("wifi_nmcli_test.turn_down_nm_connections")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch(
        "wifi_nmcli_test.list_aps",
        return_value={
            "SSID1": {"Chan": "1", "Freq": "2412", "Signal": "60"},
            "SSID2": {"Chan": "6", "Freq": "2437", "Signal": "70"},
            "SSID3": {"Chan": "11", "Freq": "2462", "Signal": "80"},
        },
    )
    @patch("wifi_nmcli_test.sys.argv", ["wifi_nmcli_test.py", "scan", "wlan0"])
    @patch("wifi_nmcli_test.device_rescan")
    def test_main_scan_aps_found(
        self,
        list_aps_mock,
        turn_up_connection_mock,
        turn_down_nm_connections_mock,
        get_nm_activate_connection_mock,
        delete_test_ap_ssid_connection_mock,
        mock_device_rescan,
    ):
        main()

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection")
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection", return_value="uuid123"
    )
    @patch("wifi_nmcli_test.turn_down_nm_connections")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch("wifi_nmcli_test.list_aps", return_value={})
    @patch(
        "wifi_nmcli_test.sys.argv",
        ["wifi_nmcli_test.py", "open", "wlan0", "TestSSID"],
    )
    @patch("wifi_nmcli_test.device_rescan")
    def test_main_open_no_aps_found(
        self,
        list_aps_mock,
        turn_up_connection_mock,
        turn_down_nm_connections_mock,
        get_nm_activate_connection_mock,
        delete_test_ap_ssid_connection_mock,
        mock_device_rescan,
    ):
        main()

    @patch("wifi_nmcli_test.delete_test_ap_ssid_connection")
    @patch(
        "wifi_nmcli_test.get_nm_activate_connection", return_value="uuid123"
    )
    @patch("wifi_nmcli_test.turn_down_nm_connections")
    @patch("wifi_nmcli_test.turn_up_connection")
    @patch(
        "wifi_nmcli_test.list_aps",
        return_value={
            "SSID1": {"Chan": "1", "Freq": "2412", "Signal": "60"},
            "SSID2": {"Chan": "6", "Freq": "2437", "Signal": "70"},
            "TestSSID": {"Chan": "11", "Freq": "2462", "Signal": "80"},
        },
    )
    @patch(
        "wifi_nmcli_test.sys.argv",
        ["wifi_nmcli_test.py", "open", "wlan0", "TestSSID"],
    )
    @patch("wifi_nmcli_test.open_connection", return_value=0)
    @patch("wifi_nmcli_test.device_rescan")
    def test_main_open_aps_found(
        self,
        list_aps_mock,
        turn_up_connection_mock,
        turn_down_nm_connections_mock,
        get_nm_activate_connection_mock,
        delete_test_ap_ssid_connection_mock,
        mock_open_connection,
        mock_device_rescan,
    ):
        main()
