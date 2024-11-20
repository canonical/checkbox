#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Eugene Wu <eugene.wu@canonical.com>
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
from unittest.mock import patch, MagicMock
from wol_check import (
    get_timestamp,
    extract_timestamp,
    get_suspend_boot_time,
    parse_args,
    main,
)


class TestGetTimestamp(unittest.TestCase):
    @patch("builtins.open")
    def test_get_timestamp_success(self, mock_open):
        mock_file = mock_open.return_value.__enter__.return_value
        mock_file.read.return_value = "1622547800.0"

        result = get_timestamp("test_file.txt")
        self.assertEqual(result, 1622547800.0)

    @patch("builtins.open")
    def test_get_timestamp_file_not_found(self, mock_open):
        mock_open.side_effect = FileNotFoundError

        with self.assertRaises(FileNotFoundError):
            get_timestamp("nonexistent_file.txt")


class TestExtractTimeStamp(unittest.TestCase):
    def test_extract_timestamp_with_timestamp(self):
        log_line = r"1734472364.392919 M70s-Gen6-1 kernel: PM: suspend exit"
        timestamp = extract_timestamp(log_line)
        self.assertEqual(timestamp, 1734472364.392919)

    def test_extract_timestamp_without_timestamp(self):
        log_line = "No timestamp here"
        timestamp = extract_timestamp(log_line)
        self.assertIsNone(timestamp)


class TestGetSuspendBootTime(unittest.TestCase):
    @patch("subprocess.check_output")
    def test_get_suspend_boot_time_s3(self, mock_check_output):
        mock_check_output.return_value = (
            r"1734472364.392919 M70s-Gen6-1 kernel: PM: suspend exit"
        )
        time = get_suspend_boot_time("s3")
        self.assertEqual(time, 1734472364.392919)

    @patch("subprocess.check_output")
    def test_get_suspend_boot_time_s5(self, mock_check_output):
        mock_check_output.return_value = (
            r"1734512121.128220 M70s kernel: Linux version 6.11.0-1009-oem"
        )
        time = get_suspend_boot_time("s5")
        self.assertEqual(time, 1734512121.128220)

    @patch("subprocess.check_output")
    def test_get_suspend_boot_time_wrong_power_type(self, mock_check_output):
        mock_check_output.return_value = (
            r"1734512121.128220 M70s kernel: Linux version 6.11.0-1009-oem"
        )
        with self.assertRaises(SystemExit) as cm:
            get_suspend_boot_time("wrong_power_type")
        self.assertEqual(
            str(cm.exception), "Invalid power type. Please use s3 or s5."
        )


class ParseArgsTests(unittest.TestCase):
    def test_parse_args_with_interface(self):
        args = [
            "--interface",
            "enp0s31f6",
            "--delay",
            "10",
            "--retry",
            "5",
            "--powertype",
            "s5",
            "--timestamp_file",
            "/tmp/time_file",
        ]
        rv = parse_args(args)
        self.assertEqual(rv.interface, "enp0s31f6")
        self.assertEqual(rv.powertype, "s5")
        self.assertEqual(rv.timestamp_file, "/tmp/time_file")
        self.assertEqual(rv.delay, 10)
        self.assertEqual(rv.retry, 5)

    def test_parse_args_with_default_value(self):
        args = ["--interface", "eth0", "--powertype", "s3"]
        rv = parse_args(args)
        self.assertEqual(rv.interface, "eth0")
        self.assertEqual(rv.powertype, "s3")
        self.assertIsNone(rv.timestamp_file)
        self.assertEqual(rv.delay, 60)
        self.assertEqual(rv.retry, 3)


class TestMain(unittest.TestCase):
    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_suspend_boot_time")
    def test_main_success(
        self, mock_get_suspend_boot_time, mock_get_timestamp, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.interface = "eth0"
        args_mock.powertype = "s3"
        args_mock.timestamp_file = "/tmp/test"
        args_mock.delay = 60
        args_mock.retry = 3
        mock_parse_args.return_value = args_mock

        mock_get_timestamp.return_value = 100.0
        mock_get_suspend_boot_time.return_value = 160.0

        # Call main function
        with self.assertLogs(level="INFO") as log_messages:
            self.assertTrue(main())

        # Verify logging messages
        self.assertIn(
            "wake-on-LAN check test started.", log_messages.output[0]
        )
        self.assertIn("Interface: eth0", log_messages.output[1])
        self.assertIn("PowerType: s3", log_messages.output[2])
        self.assertIn("wake-on-LAN workes well.", log_messages.output[3])

    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_suspend_boot_time")
    def test_main_wakeonlan_fail_too_large_difference(
        self, mock_get_suspend_boot_time, mock_get_timestamp, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.interface = "eth0"
        args_mock.powertype = "s3"
        args_mock.timestamp_file = "/tmp/test"
        args_mock.delay = 60
        args_mock.retry = 3
        mock_parse_args.return_value = args_mock

        mock_get_timestamp.return_value = 100.0
        mock_get_suspend_boot_time.return_value = 400.0

        # Expect SystemExit exception with specific message
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception),
            "The system took much longer than expected to wake up,"
            "and it wasn't awakened by wake-on-LAN.",
        )

    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_suspend_boot_time")
    def test_main_wakeonlan_fail_negative_difference(
        self, mock_get_suspend_boot_time, mock_get_timestamp, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.interface = "eth0"
        args_mock.powertype = "s3"
        args_mock.timestamp_file = "/tmp/test"
        args_mock.delay = 60
        args_mock.retry = 3
        mock_parse_args.return_value = args_mock

        mock_get_timestamp.return_value = 150.0
        mock_get_suspend_boot_time.return_value = 100.0

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception), "System resume up earlier than expected."
        )


if __name__ == "__main__":
    unittest.main()
