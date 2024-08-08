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
from unittest.mock import patch

from wifi_nmcli_test import legacy_nmcli, perform_ping_test


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
        subprocess_mock.check_output.return_value = b""
        ping_mock.return_value = {
            "transmitted": 10,
            "received": 0,
            "pct_loss": 0,
        }
        self.assertFalse(perform_ping_test("wlo1"))
