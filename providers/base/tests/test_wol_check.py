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
from unittest.mock import patch, MagicMock, mock_open
from wol_check import (
    get_timestamp,
    extract_timestamp,
    get_wakeup_timestamp,
    get_system_boot_time,
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


class TestGetSystemBootTime(unittest.TestCase):
    @patch("builtins.open")
    def test_get_system_boot_time_success(self, mock_open):
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.__iter__.return_value = ["btime 1618912536\n"]
        mock_open.return_value = mock_file

        boot_time = get_system_boot_time()
        self.assertEqual(boot_time, 1618912536.0)

    @patch(
        "builtins.open", new_callable=mock_open, read_data="some other data\n"
    )
    def test_get_system_boot_time_no_btime(self, mock_file):
        with self.assertLogs(level="ERROR") as log:
            boot_time = get_system_boot_time()
            self.assertIsNone(boot_time)
            self.assertIn("cannot find btime", log.output[0])

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_system_boot_time_file_not_found(self, mock_file):
        with self.assertLogs(level="ERROR") as log:
            boot_time = get_system_boot_time()
            self.assertIsNone(boot_time)
            self.assertIn("cannot open /proc/stat.", log.output[0])

    @patch("builtins.open", side_effect=Exception("some error"))
    def test_get_system_boot_time_exception(self, mock_file):
        with self.assertLogs(level="ERROR") as log:
            boot_time = get_system_boot_time()
            self.assertIsNone(boot_time)
            self.assertIn("error while read btime: some error", log.output[0])


class TestGetWakeupTimestamp(unittest.TestCase):

    @patch("subprocess.check_output")
    def test_get_wakeup_timestamp(self, mock_check_output):
        mock_check_output.return_value = (
            r"1734472364.392919 M70s-Gen6-1 kernel: PM: suspend exit"
        )
        result = get_wakeup_timestamp()

        self.assertEqual(result, 1734472364.392919)

    @patch("subprocess.check_output")
    def test_get_wakeup_timestamp_fail(self, mock_check_output):
        mock_check_output.return_value = (
            r"1734472364.392919 M70s-Gen6-1 kernel: PM: no s3 key word"
        )
        result = get_wakeup_timestamp()

        self.assertEqual(result, None)


class ParseArgsTests(unittest.TestCase):
    def test_parse_args(self):
        args = [
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
        self.assertEqual(rv.powertype, "s5")
        self.assertEqual(rv.timestamp_file, "/tmp/time_file")
        self.assertEqual(rv.delay, 10)
        self.assertEqual(rv.retry, 5)

    def test_parse_args_with_default_value(self):
        args = ["--powertype", "s3"]
        rv = parse_args(args)
        self.assertEqual(rv.powertype, "s3")
        self.assertIsNone(rv.timestamp_file)
        self.assertEqual(rv.delay, 60)
        self.assertEqual(rv.retry, 3)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.args_mock = MagicMock()
        self.args_mock.powertype = "s3"
        self.args_mock.timestamp_file = "/tmp/test"
        self.args_mock.delay = 60
        self.args_mock.retry = 3

    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_wakeup_timestamp")
    def test_main_success(
        self, mock_get_wakeup_timestamp, mock_get_timestamp, mock_parse_args
    ):
        mock_parse_args.return_value = self.args_mock
        mock_get_timestamp.return_value = 100.0
        mock_get_wakeup_timestamp.return_value = 160.0

        # Call main function
        with self.assertLogs(level="INFO") as log_messages:
            self.assertTrue(main())

        # Verify logging messages
        self.assertIn(
            "wake-on-LAN check test started.", log_messages.output[0]
        )
        self.assertIn("PowerType: s3", log_messages.output[1])
        self.assertIn("wake-on-LAN works well.", log_messages.output[2])

    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_wakeup_timestamp")
    def test_main_wakeonlan_fail_too_large_difference(
        self, mock_get_wakeup_timestamp, mock_get_timestamp, mock_parse_args
    ):
        mock_parse_args.return_value = self.args_mock
        mock_get_timestamp.return_value = 100.0
        mock_get_wakeup_timestamp.return_value = 400.0

        # Expect SystemExit exception with specific message
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception),
            "The system took much longer than expected to wake up,"
            " and it wasn't awakened by wake-on-LAN.",
        )

    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_wakeup_timestamp")
    def test_main_wakeonlan_fail_negative_difference(
        self, mock_get_wakeup_timestamp, mock_get_timestamp, mock_parse_args
    ):
        mock_parse_args.return_value = self.args_mock
        mock_get_timestamp.return_value = 150.0
        mock_get_wakeup_timestamp.return_value = 100.0

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception), "System resumed earlier than expected."
        )

    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_wakeup_timestamp")
    def test_main_get_timestamp_none(
        self, mock_get_wakeup_timestamp, mock_get_timestamp, mock_parse_args
    ):
        mock_parse_args.return_value = self.args_mock
        mock_get_timestamp.return_value = None
        mock_get_wakeup_timestamp.return_value = 100.0

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception),
            "Couldn't get the test start time from timestamp file.",
        )

    @patch("wol_check.parse_args")
    @patch("wol_check.get_timestamp")
    @patch("wol_check.get_wakeup_timestamp")
    def test_main_get_systembacktime_none(
        self, mock_get_wakeup_timestamp, mock_get_timestamp, mock_parse_args
    ):
        mock_parse_args.return_value = self.args_mock
        mock_get_timestamp.return_value = 100.0
        mock_get_wakeup_timestamp.return_value = None

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(str(cm.exception), "Couldn't get system back time.")


if __name__ == "__main__":
    unittest.main()
