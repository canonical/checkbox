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
from subprocess import TimeoutExpired
from unittest.mock import patch

from wifi_nmcli_test import (
    hotspot,
    legacy_nmcli,
    list_aps,
    open_connection,
    parse_args,
    perform_ping_test,
    secured_connection,
    wait_for_connected,
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

    @patch("wifi_nmcli_test.ping")
    @patch("wifi_nmcli_test.sp")
    def test_perform_ping_test_true(self, subprocess_mock, ping_mock):
        subprocess_mock.check_output.return_value = b"10.0.0.1"
        ping_mock.return_value = {
            "transmitted": 10,
            "received": 5,
            "pct_loss": 0,
        }
        self.assertTrue(perform_ping_test("wlo1"))

    @patch("wifi_nmcli_test.sp")
    def test_perform_ping_test_no_target(self, subprocess_mock):
        subprocess_mock.check_output.return_value = b""
        self.assertFalse(perform_ping_test("wlo1"))

    @patch("wifi_nmcli_test.ping")
    @patch("wifi_nmcli_test.sp")
    def test_perform_ping_test_received_none(self, subprocess_mock, ping_mock):
        subprocess_mock.check_output.return_value = b"10.0.0.1"
        ping_mock.return_value = {
            "transmitted": 10,
            "received": 0,
            "pct_loss": 0,
        }
        self.assertFalse(perform_ping_test("wlo1"))

    @patch("wifi_nmcli_test.sp")
    def test_list_aps_found(self, subprocess_mock):
        args = parse_args(["scan", "wlo1"])
        subprocess_mock.check_output.return_value = b"Mock:6:2437 MHz:84"
        self.assertEqual(list_aps(args), 1)

    @patch("wifi_nmcli_test.sp")
    def test_list_aps_skip_extra_line(self, subprocess_mock):
        args = parse_args(["scan", "wlo1"])
        subprocess_mock.check_output.return_value = b"wlo1\nMock:6:2437 MHz:84"
        self.assertEqual(list_aps(args), 1)

    @patch("wifi_nmcli_test.sp")
    def test_list_aps_found_essid(self, subprocess_mock):
        args = parse_args(["open", "wlo1", "Mock"])
        subprocess_mock.check_output.return_value = (
            b"Mock:6:2437 MHz:84\nWrong:6:2437 MHz:84"
        )
        self.assertEqual(list_aps(args), 1)

    @patch("wifi_nmcli_test.sp")
    def test_list_aps_none(self, subprocess_mock):
        args = parse_args(["scan", "wlo1"])
        subprocess_mock.check_output.return_value = b""
        self.assertEqual(list_aps(args), 0)

    @patch("wifi_nmcli_test.sp")
    def test_wait_for_connected_true(self, subprocess_mock):
        subprocess_mock.check_output.return_value = b"100 (connected)"
        self.assertTrue(wait_for_connected("wlo1"))

    @patch("wifi_nmcli_test.sp")
    def test_wait_for_connected_false(self, subprocess_mock):
        subprocess_mock.check_output.return_value = b"20 (unavailable)"
        max_wait = 5
        result = wait_for_connected("wlo1", max_wait)
        self.assertEqual(subprocess_mock.check_output.call_count, max_wait)
        self.assertFalse(result)

    @patch("wifi_nmcli_test.sp")
    def test_hotspot_success(self, subprocess_mock):
        args = parse_args(["ap", "wlo1", "a"])
        subprocess_mock.call.side_effect = [0, 0, 0, 0]
        self.assertEqual(hotspot(args), 0)

    @patch("wifi_nmcli_test.sp")
    def test_hotspot_creation_fail(self, subprocess_mock):
        args = parse_args(["ap", "wlo1", "a"])
        subprocess_mock.call.side_effect = [2, 0, 0, 0]
        self.assertEqual(hotspot(args), 2)

    @patch("wifi_nmcli_test.sp")
    def test_hotspot_set_band_fail(self, subprocess_mock):
        args = parse_args(["ap", "wlo1", "a"])
        subprocess_mock.call.side_effect = [0, 2, 0, 0]
        self.assertEqual(hotspot(args), 2)

    @patch("wifi_nmcli_test.sp")
    def test_hotspot_security_fail(self, subprocess_mock):
        args = parse_args(["ap", "wlo1", "a"])
        subprocess_mock.call.side_effect = [0, 0, 2, 0]
        self.assertEqual(hotspot(args), 2)

    @patch("wifi_nmcli_test.sp")
    def test_hotspot_connection_fail(self, subprocess_mock):
        args = parse_args(["ap", "wlo1", "a"])
        subprocess_mock.call.side_effect = [0, 0, 0, 10]
        self.assertEqual(hotspot(args), 10)

    @patch("wifi_nmcli_test.perform_ping_test")
    @patch("wifi_nmcli_test.wait_for_connected")
    @patch("wifi_nmcli_test.legacy_nmcli")
    @patch("wifi_nmcli_test.sp")
    def test_open_connection_success(
        self,
        subprocess_mock,
        legacy_nmcli_mock,
        wait_for_connected_mock,
        perform_ping_test_mock,
    ):
        args = parse_args(["open", "wlo1", "Mock"])
        subprocess_mock.call.side_effect = [0, 0, 0, 0]
        legacy_nmcli_mock.return_value = False
        wait_for_connected_mock.return_value = True
        perform_ping_test_mock.return_value = True
        self.assertEqual(open_connection(args), 0)

    @patch("wifi_nmcli_test.wait_for_connected")
    @patch("wifi_nmcli_test.legacy_nmcli")
    @patch("wifi_nmcli_test.sp")
    def test_open_connection_legacy_timeout(
        self,
        subprocess_mock,
        legacy_nmcli_mock,
        wait_for_connected_mock,
    ):
        args = parse_args(["open", "wlo1", "Mock"])

        subprocess_mock.TimeoutExpired = TimeoutExpired
        subprocess_mock.call.side_effect = [
            0,
            subprocess_mock.TimeoutExpired("nmcli c up TEST_CON", 200),
        ]
        legacy_nmcli_mock.return_value = True
        wait_for_connected_mock.return_value = False

        self.assertEqual(open_connection(args), 1)

    @patch("wifi_nmcli_test.perform_ping_test")
    @patch("wifi_nmcli_test.wait_for_connected")
    @patch("wifi_nmcli_test.legacy_nmcli")
    @patch("wifi_nmcli_test.sp")
    def test_open_connection_ping_fail(
        self,
        subprocess_mock,
        legacy_nmcli_mock,
        wait_for_connected_mock,
        perform_ping_test_mock,
    ):
        args = parse_args(["open", "wlo1", "Mock"])

        subprocess_mock.call.side_effect = [0, 0, 0, 0]
        legacy_nmcli_mock.return_value = False
        wait_for_connected_mock.return_value = True
        perform_ping_test_mock.return_value = False

        self.assertEqual(open_connection(args), 1)

    @patch("wifi_nmcli_test.perform_ping_test")
    @patch("wifi_nmcli_test.wait_for_connected")
    @patch("wifi_nmcli_test.legacy_nmcli")
    @patch("wifi_nmcli_test.sp")
    def test_secured_connection_success(
        self,
        subprocess_mock,
        legacy_nmcli_mock,
        wait_for_connected_mock,
        perform_ping_test_mock,
    ):
        args = parse_args(["secured", "wlo1", "Mock", "password"])
        subprocess_mock.call.side_effect = [0, 0, 0, 0]
        legacy_nmcli_mock.return_value = False
        wait_for_connected_mock.return_value = True
        perform_ping_test_mock.return_value = True
        self.assertEqual(secured_connection(args), 0)

    @patch("wifi_nmcli_test.wait_for_connected")
    @patch("wifi_nmcli_test.legacy_nmcli")
    @patch("wifi_nmcli_test.sp")
    def test_secured_connection_legacy_timeout(
        self,
        subprocess_mock,
        legacy_nmcli_mock,
        wait_for_connected_mock,
    ):
        args = parse_args(["secured", "wlo1", "Mock", "password"])

        subprocess_mock.TimeoutExpired = TimeoutError
        subprocess_mock.call.side_effect = [
            0,
            subprocess_mock.TimeoutExpired("nmcli c up TEST_CON", 200),
        ]
        legacy_nmcli_mock.return_value = True
        wait_for_connected_mock.return_value = False

        self.assertEqual(secured_connection(args), 1)

    @patch("wifi_nmcli_test.perform_ping_test")
    @patch("wifi_nmcli_test.wait_for_connected")
    @patch("wifi_nmcli_test.legacy_nmcli")
    @patch("wifi_nmcli_test.sp")
    def test_secured_connection_ping_fail(
        self,
        subprocess_mock,
        legacy_nmcli_mock,
        wait_for_connected_mock,
        perform_ping_test_mock,
    ):
        args = parse_args(["secured", "wlo1", "Mock", "password"])

        subprocess_mock.call.side_effect = [0, 0, 0, 0]
        legacy_nmcli_mock.return_value = False
        wait_for_connected_mock.return_value = True
        perform_ping_test_mock.return_value = False

        self.assertEqual(secured_connection(args), 1)
