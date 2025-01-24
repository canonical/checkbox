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
import unittest

from suspend_stats import SuspendStats


class TestSuspendStats(unittest.TestCase):
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open, read_data="1\n")
    def test_collect_content_under_directory(self, mock_file, mock_os_walk):
        mock_os_walk.return_value = [
            (
                "/sys/power/suspend_stats/",
                [],
                ["success", "failed_suspend", "fail", "last_failed_dev"],
            ),
        ]

        stats = SuspendStats()
        expected_content = {
            "success": "1",
            "failed_suspend": "1",
            "fail": "1",
            "last_failed_dev": "1",
        }

        self.assertEqual(stats.contents, expected_content)

    def test_is_after_suspend(self):
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
        self.assertFalse(stats.is_after_suspend())

        stats.contents["failed_prepare"] = "0"
        stats.contents["failed_suspend"] = "1"
        self.assertFalse(stats.is_after_suspend())

        stats.contents["failed_suspend"] = "0"
        stats.contents["failed_resume"] = "1"
        self.assertFalse(stats.is_after_suspend())

    def test_is_any_failed(self):
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

    def test_parse_args_valid(self):
        stats = SuspendStats()
        args = ["valid", "--print"]
        rv = stats.parse_args(args)

        self.assertEqual(rv.type, "valid")
        self.assertTrue(rv.print)

    def test_parse_args_any(self):
        stats = SuspendStats()
        args = ["any", "--print"]
        rv = stats.parse_args(args)

        self.assertEqual(rv.type, "any")
        self.assertTrue(rv.print)


class MainTests(unittest.TestCase):
    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_after_suspend")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_valid_succ(self, mock_print, mock_after, mock_parse_args):
        args_mock = MagicMock()
        args_mock.type = "valid"
        args_mock.print = True
        mock_parse_args.return_value = args_mock
        mock_after.return_value = True
        self.assertEqual(SuspendStats().main(), None)

    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_after_suspend")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_valid_fail(self, mock_print, mock_after, mock_parse_args):
        args_mock = MagicMock()
        args_mock.type = "valid"
        args_mock.print = False
        mock_parse_args.return_value = args_mock
        mock_after.return_value = False
        with self.assertRaises(SystemExit):
            SuspendStats().main()

    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_any_failed")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_any_succ(
        self, mock_print, mock_any, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.type = "any"
        args_mock.print = False
        mock_parse_args.return_value = args_mock
        mock_any.return_value = False
        self.assertEqual(SuspendStats().main(), None)

    @patch("suspend_stats.SuspendStats.parse_args")
    @patch("suspend_stats.SuspendStats.is_any_failed")
    @patch("suspend_stats.SuspendStats.print_all_content")
    def test_run_any_fail(
        self, mock_print, mock_any, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.type = "any"
        args_mock.print = True
        mock_parse_args.return_value = args_mock
        mock_any.return_value = True
        with self.assertRaises(SystemExit):
            SuspendStats().main()

    @patch("suspend_stats.SuspendStats.parse_args")
    def test_run_nothing(self, mock_parse_args):
        args_mock = MagicMock()
        args_mock.type = "Unknown"
        args_mock.print = False
        args_mock.raise_exit = False
        mock_parse_args.return_value = args_mock
        self.assertEqual(SuspendStats().main(), None)


if __name__ == "__main__":
    unittest.main()
