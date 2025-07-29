#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import tempfile
import unittest

from suspend_stats import SuspendStats

debugfs = """
success: 1
fail: 0
failed_freeze: 0
failed_prepare: 0
failed_suspend: 0
failed_suspend_late: 0
failed_suspend_noirq: 0
failed_resume: 0
failed_resume_early: 0
failed_resume_noirq: 0
failures:
  last_failed_dev:	
			
  last_failed_errno:	0
			0
  last_failed_step:
"""


class TestSuspendStats(unittest.TestCase):
    @patch("suspend_stats.SuspendStats.collect_content_under_directory")
    @patch("suspend_stats.SuspendStats.parse_suspend_stats_in_debugfs")
    def test_init_with_existing_directory(self, mock_parse, mock_collect):
        mock_collect.return_value = "mocked content"

        collector = SuspendStats()

        mock_collect.assert_called_once_with("/sys/power/suspend_stats/")
        self.assertIsNotNone(collector)

    @patch("suspend_stats.SuspendStats.collect_content_under_directory")
    @patch("suspend_stats.SuspendStats.parse_suspend_stats_in_debugfs")
    def test_init_with_non_existing_directory(self, mock_parse, mock_collect):
        mock_collect.side_effect = FileNotFoundError
        mock_parse.return_value = "parsed debugfs content"

        SuspendStats()

        mock_collect.assert_called_once_with("/sys/power/suspend_stats/")
        mock_parse.assert_called_once_with()

    @patch("suspend_stats.SuspendStats.__init__")
    @patch("builtins.open", new_callable=mock_open, read_data=debugfs)
    def test_parse_suspend_stats(self, mock_file, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        expected_output = {
            "success": "1",
            "fail": "0",
            "failed_freeze": "0",
            "failed_prepare": "0",
            "failed_suspend": "0",
            "failed_suspend_late": "0",
            "failed_suspend_noirq": "0",
            "failed_resume": "0",
            "failed_resume_early": "0",
            "failed_resume_noirq": "0",
            "last_failed_dev": "",
            "last_failed_errno": "0",
            "last_failed_step": "",
        }
        result = stats.parse_suspend_stats_in_debugfs()
        self.assertEqual(result, expected_output)

    @patch("suspend_stats.SuspendStats.__init__")
    def test_empty_directory(self, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertEqual(
                stats.collect_content_under_directory(tmp_dir), {}
            )

    @patch("suspend_stats.SuspendStats.__init__")
    def test_single_file(self, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test.txt"
            file_path.write_text("Line1\nLine2")

            result = stats.collect_content_under_directory(tmp_dir)
            self.assertEqual(result, {"test.txt": "Line1"})

    @patch("suspend_stats.SuspendStats.__init__")
    def test_multiple_files(self, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path_1 = Path(tmp_dir) / "file1.txt"
            file_path_2 = Path(tmp_dir) / "file2.txt"

            file_path_1.write_text("Line11\nLine12")
            file_path_2.write_text("Line21\nLine22")

            result = stats.collect_content_under_directory(tmp_dir)
            self.assertEqual(
                result, {"file1.txt": "Line11", "file2.txt": "Line21"}
            )

    @patch("suspend_stats.SuspendStats.__init__")
    @patch("pathlib.Path.iterdir")
    def test_invalid_search_directories(self, mock_path, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        mock_path.side_effect = FileNotFoundError

        with self.assertRaises(FileNotFoundError):
            stats.collect_content_under_directory("/non/existent/directory")

    @patch("suspend_stats.SuspendStats.__init__")
    def test_is_after_suspend(self, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        stats.contents = {
            "success": "1",
            "failed_prepare": "0",
            "failed_suspend": "0",
            "failed_resume": "0",
            "fail": "0",
            "last_failed_dev": "",
        }
        self.assertTrue(stats.is_after_suspend())

        stats.contents["failed_prepare"] = "1"
        self.assertTrue(stats.is_after_suspend())

        stats.contents["failed_prepare"] = "0"
        stats.contents["failed_suspend"] = "1"
        self.assertTrue(stats.is_after_suspend())

        stats.contents["failed_suspend"] = "0"
        stats.contents["failed_resume"] = "1"
        self.assertTrue(stats.is_after_suspend())

    @patch("suspend_stats.SuspendStats.__init__")
    def test_is_any_failed(self, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        stats.contents = {
            "success": "1",
            "failed_suspend": "0",
            "fail": "1",
            "last_failed_dev": "",
        }
        self.assertTrue(stats.is_any_failed())

        stats.contents["fail"] = "0"
        self.assertFalse(stats.is_any_failed())

        stats.contents["failed_prepare"] = "1"
        self.assertTrue(stats.is_any_failed())

        stats.contents["failed_prepare"] = "0"
        stats.contents["failed_suspend"] = "1"
        self.assertTrue(stats.is_any_failed())

        stats.contents["failed_suspend"] = "0"
        stats.contents["failed_resume"] = "1"
        self.assertTrue(stats.is_any_failed())

    @patch("suspend_stats.SuspendStats.__init__")
    def test_parse_args_valid(self, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        args = ["after_suspend"]
        rv = stats.parse_args(args)

        self.assertEqual(rv.check_type, "after_suspend")

    @patch("suspend_stats.SuspendStats.__init__")
    def test_parse_args_any(self, mock_init):
        mock_init.return_value = None
        stats = SuspendStats()
        args = ["any_failure"]
        rv = stats.parse_args(args)

        self.assertEqual(rv.check_type, "any_failure")


class MainTests(unittest.TestCase):
    @patch("suspend_stats.SuspendStats.__init__")
    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_after_suspend")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_valid_succ(
        self, mock_print, mock_after, mock_parse_args, mock_init
    ):
        mock_init.return_value = None
        args_mock = MagicMock()
        args_mock.check_type = "after_suspend"
        mock_parse_args.return_value = args_mock
        mock_after.return_value = True
        self.assertEqual(SuspendStats().main(), None)

    @patch("suspend_stats.SuspendStats.__init__")
    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_after_suspend")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_valid_fail(
        self, mock_print, mock_after, mock_parse_args, mock_init
    ):
        mock_init.return_value = None
        args_mock = MagicMock()
        args_mock.check_type = "after_suspend"
        mock_parse_args.return_value = args_mock
        mock_after.return_value = False
        with self.assertRaises(SystemExit):
            SuspendStats().main()

    @patch("suspend_stats.SuspendStats.__init__")
    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_any_failed")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_any_succ(
        self, mock_print, mock_any, mock_parse_args, mock_init
    ):
        mock_init.return_value = None
        args_mock = MagicMock()
        args_mock.check_type = "any_failure"
        mock_parse_args.return_value = args_mock
        mock_any.return_value = False
        self.assertEqual(SuspendStats().main(), None)

    @patch("suspend_stats.SuspendStats.__init__")
    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_any_failed")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_any_fail(
        self, mock_print, mock_any, mock_parse_args, mock_init
    ):
        mock_init.return_value = None
        args_mock = MagicMock()
        args_mock.check_type = "any_failure"
        mock_parse_args.return_value = args_mock
        mock_any.return_value = True
        stats = SuspendStats()
        stats.contents["fail"] = "0"
        with self.assertRaises(SystemExit):
            stats.main()


if __name__ == "__main__":
    unittest.main()
