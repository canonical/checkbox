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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import subprocess
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, mock_open, patch

import idle_suspend
from idle_suspend import (
    _find_ac_online_path,
    _parse_ts,
    build_parser,
    check_power_mode,
    get_journal_since,
    log_timestamp,
    parse_journal_suspend_times,
    run_cmd,
)

UTC = timezone.utc

_UNSET = object()

# Reusable timestamp fixtures
_TS1 = "2026-04-17T03:00:00+00:00"
_TS2 = "2026-04-17T03:05:00+00:00"
_TS3 = "2026-04-17T03:10:00+00:00"
_TS1_DT = datetime(2026, 4, 17, 3, 0, 0, tzinfo=UTC)
_TS2_DT = datetime(2026, 4, 17, 3, 5, 0, tzinfo=UTC)
_TS3_DT = datetime(2026, 4, 17, 3, 10, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# run_cmd
# ---------------------------------------------------------------------------


class TestRunCmd(unittest.TestCase):
    def _make_result(self, returncode=0, stdout="", stderr=""):
        r = MagicMock()
        r.returncode = returncode
        r.stdout = stdout
        r.stderr = stderr
        return r

    def test_success_returns_stripped_stdout(self):
        with patch(
            "subprocess.run",
            return_value=self._make_result(stdout="  hello  \n"),
        ):
            self.assertEqual(run_cmd(["echo", "hello"]), "hello")

    def test_failure_raises_runtime_error_when_check_true(self):
        with patch(
            "subprocess.run",
            return_value=self._make_result(returncode=1, stderr="oops"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                run_cmd(["false"])
        self.assertIn("oops", str(ctx.exception))

    def test_failure_no_raise_when_check_false(self):
        with patch(
            "subprocess.run",
            return_value=self._make_result(returncode=1, stdout="  out  "),
        ):
            self.assertEqual(run_cmd(["false"], check=False), "out")

    def test_subprocess_called_with_correct_kwargs(self):
        with patch(
            "subprocess.run",
            return_value=self._make_result(),
        ) as mock_run:
            run_cmd(["ls"])
        _, kwargs = mock_run.call_args
        self.assertEqual(kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(kwargs["stderr"], subprocess.PIPE)
        self.assertTrue(kwargs["universal_newlines"])

    def test_empty_stdout_returns_empty_string(self):
        with patch(
            "subprocess.run", return_value=self._make_result(stdout="")
        ):
            self.assertEqual(run_cmd(["true"]), "")


# ---------------------------------------------------------------------------
# _find_ac_online_path
# ---------------------------------------------------------------------------


class TestFindAcOnlinePath(unittest.TestCase):
    def test_returns_first_match_from_first_glob(self):
        def fake_glob(pattern):
            if "ADP*" in pattern:
                return ["/sys/class/power_supply/ADP0/online"]
            return []

        with patch("idle_suspend.glob.glob", side_effect=fake_glob):
            self.assertEqual(
                _find_ac_online_path(),
                "/sys/class/power_supply/ADP0/online",
            )

    def test_falls_through_to_second_pattern(self):
        def fake_glob(pattern):
            if "AC*" in pattern and "ADP*" not in pattern:
                return ["/sys/class/power_supply/AC0/online"]
            return []

        with patch("idle_suspend.glob.glob", side_effect=fake_glob):
            self.assertEqual(
                _find_ac_online_path(),
                "/sys/class/power_supply/AC0/online",
            )

    def test_returns_none_when_no_glob_matches(self):
        with patch("idle_suspend.glob.glob", return_value=[]):
            self.assertIsNone(_find_ac_online_path())

    def test_returns_first_of_multiple_matches(self):
        paths = [
            "/sys/class/power_supply/ADP0/online",
            "/sys/class/power_supply/ADP1/online",
        ]
        with patch("idle_suspend.glob.glob", return_value=paths):
            self.assertEqual(_find_ac_online_path(), paths[0])


# ---------------------------------------------------------------------------
# check_power_mode
# ---------------------------------------------------------------------------


class TestCheckPowerMode(unittest.TestCase):
    def _patch_path(self, path):
        return patch("idle_suspend._find_ac_online_path", return_value=path)

    def test_no_ac_path_raises_systemexit(self):
        with self._patch_path(None):
            with self.assertRaises(SystemExit) as ctx:
                check_power_mode("ac")
        self.assertIn("Cannot determine", str(ctx.exception))

    def test_oserror_reading_file_raises_systemexit(self):
        with self._patch_path("/fake/path"):
            with patch("builtins.open", side_effect=OSError("no perm")):
                with self.assertRaises(SystemExit) as ctx:
                    check_power_mode("ac")
        self.assertIn("Cannot read power status", str(ctx.exception))

    def test_ac_mode_on_ac_does_not_raise(self):
        with self._patch_path("/fake/path"):
            with patch("builtins.open", mock_open(read_data="1\n")):
                check_power_mode("ac")  # must not raise

    def test_ac_mode_on_battery_raises(self):
        with self._patch_path("/fake/path"):
            with patch("builtins.open", mock_open(read_data="0\n")):
                with self.assertRaises(SystemExit) as ctx:
                    check_power_mode("ac")
        self.assertIn("battery", str(ctx.exception))

    def test_battery_mode_on_battery_does_not_raise(self):
        with self._patch_path("/fake/path"):
            with patch("builtins.open", mock_open(read_data="0\n")):
                check_power_mode("battery")  # must not raise

    def test_battery_mode_on_ac_raises(self):
        with self._patch_path("/fake/path"):
            with patch("builtins.open", mock_open(read_data="1\n")):
                with self.assertRaises(SystemExit) as ctx:
                    check_power_mode("battery")
        self.assertIn("AC power", str(ctx.exception))


# ---------------------------------------------------------------------------
# log_timestamp
# ---------------------------------------------------------------------------


class TestLogTimestamp(unittest.TestCase):
    def test_returns_aware_utc_datetime(self):
        with patch("idle_suspend.run_cmd"):
            result = log_timestamp()
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.tzinfo, UTC)

    def test_calls_logger_with_tag(self):
        with patch("idle_suspend.run_cmd") as mock_run:
            log_timestamp()
        cmd = mock_run.call_args[0][0]
        self.assertIn("logger", cmd)
        self.assertIn("-t", cmd)
        self.assertIn(idle_suspend.LOGGER_TAG, cmd)

    def test_message_contains_start_marker(self):
        with patch("idle_suspend.run_cmd") as mock_run:
            log_timestamp()
        cmd = mock_run.call_args[0][0]
        self.assertTrue(any("SUSPEND_TEST_START" in arg for arg in cmd))

    def test_timestamp_in_message_matches_returned_value(self):
        with patch("idle_suspend.run_cmd") as mock_run:
            result = log_timestamp()
        cmd = mock_run.call_args[0][0]
        ts_str = result.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue(any(ts_str in arg for arg in cmd))


# ---------------------------------------------------------------------------
# get_journal_since
# ---------------------------------------------------------------------------


class TestGetJournalSince(unittest.TestCase):
    _since = datetime(2026, 4, 17, 3, 0, 0, tzinfo=UTC)

    def test_calls_journalctl_with_since_arg(self):
        with patch("idle_suspend.run_cmd", return_value="") as mock_run:
            get_journal_since(self._since)
        cmd = mock_run.call_args[0][0]
        self.assertIn("journalctl", cmd)
        self.assertIn("--since", cmd)
        idx = cmd.index("--since")
        self.assertEqual(cmd[idx + 1], "2026-04-17 03:00:00")

    def test_uses_check_false(self):
        with patch("idle_suspend.run_cmd", return_value="") as mock_run:
            get_journal_since(self._since)
        kwargs = mock_run.call_args[1]
        self.assertFalse(kwargs.get("check", True))

    def test_returns_run_cmd_output(self):
        with patch("idle_suspend.run_cmd", return_value="journal output"):
            result = get_journal_since(self._since)
        self.assertEqual(result, "journal output")

    def test_short_iso_format_requested(self):
        with patch("idle_suspend.run_cmd", return_value="") as mock_run:
            get_journal_since(self._since)
        cmd = mock_run.call_args[0][0]
        self.assertIn("short-iso", cmd)


# ---------------------------------------------------------------------------
# _parse_ts
# ---------------------------------------------------------------------------


class TestParseTs(unittest.TestCase):
    def test_utc_zero_offset(self):
        result = _parse_ts("2026-04-17T03:00:00+00:00")
        self.assertEqual(result, _TS1_DT)

    def test_positive_offset_converted_to_utc(self):
        # 08:30+05:30 == 03:00 UTC
        result = _parse_ts("2026-04-17T08:30:00+05:30")
        self.assertEqual(result, _TS1_DT)

    def test_negative_offset_converted_to_utc(self):
        # 22:00-05:00 == 03:00 UTC next day
        result = _parse_ts("2026-04-16T22:00:00-05:00")
        self.assertEqual(result, _TS1_DT)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_parse_ts("not-a-timestamp"))

    def test_date_only_returns_none(self):
        self.assertIsNone(_parse_ts("2026-04-17"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_ts(""))

    def test_result_is_datetime(self):
        result = _parse_ts("2026-04-17T03:00:00+00:00")
        self.assertIsInstance(result, datetime)


# ---------------------------------------------------------------------------
# parse_journal_suspend_times
# ---------------------------------------------------------------------------


def _jline(ts, msg):
    """Build a fake journal line with the given timestamp and message."""
    return "{} hostname kernel: {}".format(ts, msg)


class TestParseJournalSuspendTimes(unittest.TestCase):
    def test_empty_input_returns_none_none(self):
        s, r = parse_journal_suspend_times("")
        self.assertIsNone(s)
        self.assertIsNone(r)

    def test_no_matching_keywords_returns_none_none(self):
        output = _jline(_TS1, "some random kernel message")
        s, r = parse_journal_suspend_times(output)
        self.assertIsNone(s)
        self.assertIsNone(r)

    def test_line_without_timestamp_is_skipped(self):
        output = "no-ts-here PM: suspend entry"
        s, r = parse_journal_suspend_times(output)
        self.assertIsNone(s)
        self.assertIsNone(r)

    # --- suspend patterns ---

    def test_suspend_entry_pattern(self):
        s, _ = parse_journal_suspend_times(_jline(_TS1, "PM: suspend entry"))
        self.assertEqual(s, _TS1_DT)

    def test_suspending_system_pattern(self):
        s, _ = parse_journal_suspend_times(_jline(_TS1, "Suspending system"))
        self.assertEqual(s, _TS1_DT)

    def test_reached_target_sleep_pattern(self):
        s, _ = parse_journal_suspend_times(
            _jline(_TS1, "Reached target Sleep")
        )
        self.assertEqual(s, _TS1_DT)

    def test_reached_target_sleep_lowercase(self):
        s, _ = parse_journal_suspend_times(
            _jline(_TS1, "Reached target sleep")
        )
        self.assertEqual(s, _TS1_DT)

    # --- resume patterns ---

    def test_suspend_exit_pattern(self):
        _, r = parse_journal_suspend_times(_jline(_TS2, "PM: suspend exit"))
        self.assertEqual(r, _TS2_DT)

    def test_pm_resume_pattern(self):
        _, r = parse_journal_suspend_times(_jline(_TS2, "PM: resume"))
        self.assertEqual(r, _TS2_DT)

    def test_finished_resume_pattern(self):
        _, r = parse_journal_suspend_times(_jline(_TS2, "Finished Resume"))
        self.assertEqual(r, _TS2_DT)

    def test_finished_resume_lowercase(self):
        _, r = parse_journal_suspend_times(_jline(_TS2, "Finished resume"))
        self.assertEqual(r, _TS2_DT)

    def test_acpi_waking_pattern(self):
        _, r = parse_journal_suspend_times(_jline(_TS2, "ACPI: Waking"))
        self.assertEqual(r, _TS2_DT)

    # --- combined / ordering ---

    def test_both_suspend_and_resume_detected(self):
        lines = "\n".join(
            [
                _jline(_TS1, "PM: suspend entry"),
                _jline(_TS2, "PM: suspend exit"),
            ]
        )
        s, r = parse_journal_suspend_times(lines)
        self.assertEqual(s, _TS1_DT)
        self.assertEqual(r, _TS2_DT)

    def test_last_suspend_occurrence_wins(self):
        lines = "\n".join(
            [
                _jline(_TS1, "PM: suspend entry"),
                _jline(_TS3, "Suspending system"),
            ]
        )
        s, _ = parse_journal_suspend_times(lines)
        self.assertEqual(s, _TS3_DT)

    def test_last_resume_occurrence_wins(self):
        lines = "\n".join(
            [
                _jline(_TS1, "PM: suspend exit"),
                _jline(_TS3, "ACPI: Waking"),
            ]
        )
        _, r = parse_journal_suspend_times(lines)
        self.assertEqual(r, _TS3_DT)

    def test_non_timestamp_lines_interspersed(self):
        lines = "\n".join(
            [
                "-- Journal begins --",
                _jline(_TS1, "PM: suspend entry"),
                "some log line without timestamp",
                _jline(_TS2, "PM: suspend exit"),
            ]
        )
        s, r = parse_journal_suspend_times(lines)
        self.assertEqual(s, _TS1_DT)
        self.assertEqual(r, _TS2_DT)

    def test_unparseable_timestamp_line_is_skipped(self):
        line = "2026-13-17T03:00:00+00:00 hostname kernel: PM: suspend entry"
        s, r = parse_journal_suspend_times(line)
        self.assertIsNone(s)
        self.assertIsNone(r)


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------


class TestBuildParser(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_returns_argument_parser(self):
        self.assertIsInstance(self.parser, argparse.ArgumentParser)

    def test_mode_required(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])

    def test_mode_ac_accepted(self):
        args = self.parser.parse_args(["--mode", "ac"])
        self.assertEqual(args.mode, "ac")

    def test_mode_battery_accepted(self):
        args = self.parser.parse_args(["--mode", "battery"])
        self.assertEqual(args.mode, "battery")

    def test_mode_invalid_raises(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--mode", "usb"])

    def test_default_suspend_time_is_15(self):
        args = self.parser.parse_args(["--mode", "ac"])
        self.assertEqual(args.suspend_time, 15)

    def test_custom_suspend_time(self):
        args = self.parser.parse_args(["--mode", "ac", "--suspend-time", "30"])
        self.assertEqual(args.suspend_time, 30)

    def test_suspend_time_is_int(self):
        args = self.parser.parse_args(["--mode", "ac"])
        self.assertIsInstance(args.suspend_time, int)

    def test_default_extra_percent_is_10(self):
        args = self.parser.parse_args(["--mode", "ac"])
        self.assertAlmostEqual(args.extra_percent, 10.0)

    def test_custom_extra_percent(self):
        args = self.parser.parse_args(
            ["--mode", "ac", "--extra-percent", "20.5"]
        )
        self.assertAlmostEqual(args.extra_percent, 20.5)

    def test_extra_percent_is_float(self):
        args = self.parser.parse_args(["--mode", "ac"])
        self.assertIsInstance(args.extra_percent, float)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain(unittest.TestCase):
    """Tests for the main() orchestration function."""

    _LOG_START = datetime(2026, 4, 17, 3, 0, 0, tzinfo=UTC)
    _SUSPEND_ON_TIME = datetime(2026, 4, 17, 3, 15, 0, tzinfo=UTC)
    _RESUME_ON_TIME = datetime(2026, 4, 17, 3, 20, 0, tzinfo=UTC)

    def _enter_patches(
        self, stack, argv=None, suspend_utc=_UNSET, resume_utc=None
    ):
        """Push all main() side-effect patches into *stack*.

        Returns a dict of named mocks for assertions.
        suspend_utc defaults to _SUSPEND_ON_TIME when not supplied.
        Pass None explicitly to simulate no suspend found.
        """
        if argv is None:
            argv = ["prog", "--mode", "ac"]
        if suspend_utc is _UNSET:
            suspend_utc = self._SUSPEND_ON_TIME
        if resume_utc is None:
            resume_utc = self._RESUME_ON_TIME
        stack.enter_context(patch("sys.argv", argv))
        mocks = {}
        mocks["check"] = stack.enter_context(
            patch("idle_suspend.check_power_mode")
        )
        stack.enter_context(
            patch(
                "idle_suspend.log_timestamp",
                return_value=self._LOG_START,
            )
        )
        mocks["sleep"] = stack.enter_context(patch("idle_suspend.time.sleep"))
        stack.enter_context(
            patch("idle_suspend.get_journal_since", return_value="")
        )
        stack.enter_context(
            patch(
                "idle_suspend.parse_journal_suspend_times",
                return_value=(suspend_utc, resume_utc),
            )
        )
        return mocks

    # --- failure branches ---

    def test_no_suspend_entry_raises_systemexit(self):
        with ExitStack() as stack:
            self._enter_patches(stack, suspend_utc=None)
            with self.assertRaises(SystemExit) as ctx:
                idle_suspend.main()
        self.assertIn("No suspend entry", str(ctx.exception))

    def test_suspend_predates_start_raises_systemexit(self):
        before = self._LOG_START - timedelta(seconds=1)
        with ExitStack() as stack:
            self._enter_patches(stack, suspend_utc=before)
            with self.assertRaises(SystemExit) as ctx:
                idle_suspend.main()
        self.assertIn("predates", str(ctx.exception))

    def test_suspend_delay_out_of_tolerance_raises_systemexit(self):
        # 900 s expected, tolerance 90 s; 1800 s actual is way outside.
        very_late = self._LOG_START + timedelta(seconds=1800)
        with ExitStack() as stack:
            self._enter_patches(stack, suspend_utc=very_late)
            with self.assertRaises(SystemExit) as ctx:
                idle_suspend.main()
        self.assertIn("Suspend delay", str(ctx.exception))

    # --- success path ---

    def test_pass_succeeds_without_exception(self):
        with ExitStack() as stack:
            self._enter_patches(stack)
            idle_suspend.main()  # must not raise

    def test_pass_prints_pass_message(self):
        with ExitStack() as stack:
            self._enter_patches(stack)
            with patch("builtins.print") as mock_print:
                idle_suspend.main()
        printed = " ".join(
            str(a) for call in mock_print.call_args_list for a in call[0]
        )
        self.assertIn("PASS", printed)

    # --- interactions ---

    def test_sleep_called_with_correct_wait_seconds(self):
        # suspend-time 15 min, extra-percent 10 → wait = 900 * 1.1 = 990 s
        with ExitStack() as stack:
            mocks = self._enter_patches(stack)
            idle_suspend.main()
        mocks["sleep"].assert_called_once()
        sleep_arg = mocks["sleep"].call_args[0][0]
        self.assertAlmostEqual(sleep_arg, 990.0)

    def test_check_power_mode_called_with_ac(self):
        with ExitStack() as stack:
            mocks = self._enter_patches(stack, argv=["prog", "--mode", "ac"])
            idle_suspend.main()
        mocks["check"].assert_called_once_with("ac")

    def test_check_power_mode_called_with_battery(self):
        with ExitStack() as stack:
            mocks = self._enter_patches(
                stack, argv=["prog", "--mode", "battery"]
            )
            idle_suspend.main()
        mocks["check"].assert_called_once_with("battery")


if __name__ == "__main__":
    unittest.main()
