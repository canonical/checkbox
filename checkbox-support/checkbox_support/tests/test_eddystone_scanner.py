#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2024 Canonical Ltd.
#
# Authors:
#     Massimiliano Girardi <massimiliano.girardi@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import unittest
from unittest.mock import patch, MagicMock

from checkbox_support.scripts import eddystone_scanner


class TestEddystoneScanner(unittest.TestCase):
    @patch("builtins.print")
    @patch("checkbox_support.scripts.eddystone_scanner.BeaconScanner")
    def test_beacon_scan_ok(self, mock_beacon_scanner, mock_print):
        class BeaconScanner:
            def __init__(self, callback, *args, **kwargs):
                self.callback = callback

            def start(self):
                packet = MagicMock(url="packet_url")
                self.callback("type", "address", "rssi", packet, None)

            def stop(self):
                pass

        mock_beacon_scanner.side_effect = BeaconScanner
        self.assertEqual(eddystone_scanner.beacon_scan("1", True), 0)
        call_args = mock_beacon_scanner.mock_calls[0].kwargs
        self.assertEqual(call_args["bt_device_id"], "1")
        self.assertEqual(call_args["debug"], True)
        mock_print.assert_called_with(
            "Eddystone beacon detected: [Adv Report Type: type] "
            "URL: packet_url <mac: address> <rssi: rssi>")

    @patch("checkbox_support.scripts.eddystone_scanner.BeaconScanner")
    @patch("time.time")
    @patch("time.sleep")
    def test_beacon_scan_fail(
        self, mock_sleep, mock_time, mock_beacon_scanner
    ):
        mock_time.side_effect = [0, 1, 60 * 60 * 60]  # 60h, trigger timeout
        self.assertEqual(eddystone_scanner.beacon_scan("1"), 1)
        mock_sleep.assert_called_with(0.5)

    @patch("checkbox_support.scripts.eddystone_scanner.BeaconScanner")
    @patch("checkbox_support.scripts.eddystone_scanner.InteractiveCommand")
    @patch("time.sleep")
    def test_main_ok(
        self, mock_sleep, mock_interactive_command, mock_beacon_scanner
    ):
        class BeaconScanner:
            def __init__(self, callback, *args, **kwargs):
                self.callback = callback

            def start(self):
                packet = MagicMock(url="packet_url")
                self.callback("type", "address", "rssi", packet, None)

            def stop(self):
                pass

        mock_beacon_scanner.side_effect = BeaconScanner
        self.assertEqual(eddystone_scanner.main(["--device", "hc1"]), 0)
