#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.


import io
import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch, call

import rtc_test


class FindRtcDevicesTests(unittest.TestCase):
    @patch("rtc_test.glob.glob")
    def test_sorts_and_strips_basenames(self, mock_glob):
        mock_glob.return_value = ["/dev/rtc1", "/dev/rtc0"]
        self.assertEqual(rtc_test.find_rtc_devices(), ["rtc0", "rtc1"])


class CanReadTests(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="123456\n")
    def test_readable_file_returns_true(self, mock_file):
        self.assertTrue(rtc_test._can_read("/fake/rtc/since_epoch"))

    @patch("builtins.open", side_effect=OSError)
    def test_unreadable_file_returns_false(self, mock_file):
        self.assertFalse(rtc_test._can_read("/fake/rtc/since_epoch"))


class CmdListTests(unittest.TestCase):
    @patch("rtc_test.find_rtc_devices", return_value=["rtc0", "rtc1"])
    def test_emits_one_record_per_device(self, mock_find):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            ret = rtc_test.cmd_list(SimpleNamespace())
        self.assertEqual(ret, 0)
        self.assertEqual(mock_stdout.getvalue(), "rtc: rtc0\n\nrtc: rtc1\n\n")


class CmdBatteryTests(unittest.TestCase):
    @patch("rtc_test.subprocess.run")
    def test_commands_has_called(self, mock_run: MagicMock):
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
        ]
        args = SimpleNamespace(rtc="rtc0", seconds=30)
        self.assertEqual(rtc_test.cmd_battery(args), 0)
        self.assertEqual(mock_run.call_count, 2)
        mock_run.assert_has_calls(
            [
                call(
                    ["rtcwake", "-v", "-d", "rtc0", "-m", "disable"],
                    check=False
                ),
                call(["rtcwake", "-v", "-d", "rtc0", "-m", "off", "-s", "30"]),
            ]
        )


class CmdNumberTests(unittest.TestCase):
    @patch("rtc_test.find_rtc_devices", return_value=["rtc0"])
    def test_number_match(self, mock_find):
        self.assertEqual(rtc_test.cmd_number(SimpleNamespace(total=1)), 0)

    @patch("rtc_test.find_rtc_devices", return_value=["rtc0"])
    def test_number_mismatch(self, mock_find):
        self.assertEqual(rtc_test.cmd_number(SimpleNamespace(total=2)), 1)

    @patch.dict(os.environ, {"TOTAL_RTC_NUM": "3"}, clear=True)
    @patch("rtc_test.find_rtc_devices", return_value=["rtc0", "rtc1", "rtc2"])
    def test_number_match_when_env_val_set(self, mock_find):
        self.assertEqual(rtc_test.cmd_number(SimpleNamespace(total=None)), 0)

    @patch.dict(os.environ, {}, clear=True)
    @patch("rtc_test.find_rtc_devices", return_value=["rtc0"])
    def test_default_when_env_val_unset(self, mock_find):
        self.assertEqual(rtc_test.cmd_number(SimpleNamespace(total=None)), 0)


class CmdReadTests(unittest.TestCase):
    @patch("rtc_test._can_read", return_value=True)
    def test_can_read(self, mock_can_read):
        self.assertEqual(rtc_test.cmd_read(SimpleNamespace(rtc="rtc0")), 0)
        mock_can_read.assert_called_once_with(
            "/sys/class/rtc/rtc0/since_epoch"
        )

    @patch("rtc_test.subprocess.run")
    @patch("rtc_test._can_read", side_effect=[False, True])
    def test_calls_hwclock_sync_when_unreadable(
        self, mock_can_read, mock_run: MagicMock
    ):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertEqual(rtc_test.cmd_read(SimpleNamespace(rtc="rtc0")), 0)
        mock_run.assert_called_once_with(
            ["hwclock", "--systohc", "--utc", "--rtc=/dev/rtc0"]
        )

    @patch("rtc_test.subprocess.run")
    @patch("rtc_test._can_read", return_value=False)
    def test_hwclock_command_itself_fails(
        self, mock_can_read, mock_run: MagicMock
    ):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertEqual(rtc_test.cmd_read(SimpleNamespace(rtc="rtc0")), 1)

    @patch("rtc_test.subprocess.run")
    @patch("rtc_test._can_read", side_effect=[False, False])
    def test_still_unreadable_after_successful_sync(
        self, mock_can_read, mock_run: MagicMock
    ):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertEqual(rtc_test.cmd_read(SimpleNamespace(rtc="rtc0")), 1)


class CmdAlarmTests(unittest.TestCase):
    @patch("rtc_test.os.path.isfile", return_value=False)
    def test_no_wakealarm_support(self, mock_isfile):
        args = SimpleNamespace(rtc="rtc0", seconds=30, timeout=60)
        self.assertEqual(rtc_test.cmd_alarm(args), 1)

    @patch("rtc_test.subprocess.run")
    @patch("rtc_test.os.path.isfile", return_value=True)
    def test_success_calls_rtcwake_with_expected_args(
        self, mock_isfile, mock_run
    ):
        args = SimpleNamespace(rtc="rtc0", seconds=30, timeout=60)
        self.assertEqual(rtc_test.cmd_alarm(args), 0)
        mock_run.assert_called_once_with(
            ["rtcwake", "-v", "-d", "rtc0", "-m", "on", "-s", "30"],
            timeout=60,
            check=True,
        )

    @patch(
        "rtc_test.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="rtcwake", timeout=60),
    )
    @patch("rtc_test.os.path.isfile", return_value=True)
    def test_timeout_is_reported_as_failure(self, mock_isfile, mock_run):
        args = SimpleNamespace(rtc="rtc0", seconds=30, timeout=60)
        self.assertEqual(rtc_test.cmd_alarm(args), 1)

    @patch(
        "rtc_test.subprocess.run",
        side_effect=subprocess.CalledProcessError(returncode=2, cmd="rtcwake"),
    )
    @patch("rtc_test.os.path.isfile", return_value=True)
    def test_nonzero_exit_is_reported_as_failure(self, mock_isfile, mock_run):
        args = SimpleNamespace(rtc="rtc0", seconds=30, timeout=60)
        self.assertEqual(rtc_test.cmd_alarm(args), 1)


class CmdClockTests(unittest.TestCase):
    @patch("rtc_test.time.time", return_value=1788854686.989309)
    @patch("builtins.open", new_callable=mock_open, read_data="1788854690\n")
    def test_within_tolerance_passes(self, mock_file, mock_time):
        args = SimpleNamespace(rtc="rtc0", tolerance=5)
        self.assertEqual(rtc_test.cmd_clock(args), 0)

    @patch("rtc_test.time.time", return_value=1788854686.989309)
    @patch("builtins.open", new_callable=mock_open, read_data="1788854688\n")
    def test_exactly_at_tolerance_passes(self, mock_file, mock_time):
        args = SimpleNamespace(rtc="rtc0", tolerance=2)
        self.assertEqual(rtc_test.cmd_clock(args), 0)

    @patch("rtc_test.time.time", return_value=1788854686.989309)
    @patch("builtins.open", new_callable=mock_open, read_data="1788854680\n")
    def test_beyond_tolerance_fails(self, mock_file, mock_time):
        args = SimpleNamespace(rtc="rtc0", tolerance=5)
        self.assertEqual(rtc_test.cmd_clock(args), 1)


class BuildParserTests(unittest.TestCase):
    def test_list_dispatches_to_cmd_list(self):
        parser = rtc_test.build_parser()
        args = parser.parse_args(["list"])
        self.assertIs(args.func, rtc_test.cmd_list)

    @patch.dict(os.environ, {"RTC_DEVICE_FILE": "rtc1"}, clear=True)
    def test_default_rtc_comes_from_env_var(self):
        parser = rtc_test.build_parser()
        args = parser.parse_args(["read"])
        self.assertEqual(args.rtc, "rtc1")

    @patch.dict(os.environ, {}, clear=True)
    def test_default_rtc_falls_back_to_rtc0(self):
        parser = rtc_test.build_parser()
        args = parser.parse_args(["clock"])
        self.assertEqual(args.rtc, "rtc0")

    def test_alarm_arguments_have_expected_defaults(self):
        parser = rtc_test.build_parser()
        args = parser.parse_args(["alarm"])
        self.assertEqual(args.seconds, 30)
        self.assertEqual(args.timeout, 60)


if __name__ == "__main__":
    unittest.main()
