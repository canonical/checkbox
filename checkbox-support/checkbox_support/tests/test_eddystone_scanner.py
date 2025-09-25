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
    @patch("checkbox_support.scripts.eddystone_scanner.BeaconScanner")
    def test_beacon_scan_ok(self, mock_beacon_scanner):
        class BeaconScanner:
            def __init__(self, callback, *args, **kwargs):
                self.callback = callback

            def start(self):
                packet = MagicMock(url="packet_url")
                self.callback("address", "rssi", packet, None)

            def stop(self):
                pass

        mock_beacon_scanner.side_effect = BeaconScanner
        self.assertEqual(eddystone_scanner.beacon_scan("1"), 0)

    @patch("checkbox_support.scripts.eddystone_scanner.BeaconScanner")
    @patch("time.time")
    @patch("time.sleep")
    def test_beacon_scan_fail(
        self, mock_sleep, mock_time, mock_beacon_scanner
    ):
        mock_time.side_effect = [0, 60 * 60 * 60]  # 60h, trigger timeout
        self.assertEqual(eddystone_scanner.beacon_scan("1"), 1)

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
                self.callback("address", "rssi", packet, None)

            def stop(self):
                pass

        mock_beacon_scanner.side_effect = BeaconScanner
        self.assertEqual(eddystone_scanner.main(["--device", "hc1"]), 0)
