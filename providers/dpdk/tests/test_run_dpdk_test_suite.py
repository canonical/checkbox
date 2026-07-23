#!/usr/bin/env python3
"""Copyright (C) 2026 Canonical Ltd.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import io
import json
import subprocess
from pathlib import Path
from unittest import TestCase
from unittest.mock import mock_open, patch

from run_dpdk_test_suite import (
    DPDK_CONFIG_SNAP_PATH,
    DPDK_SNAP_BIN,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TIMEOUT,
    DTSRunner,
    main,
)

DPDK_RESULTS = {
    "test_runs": [
        {
            "test_suites": [
                {
                    "test_suite_name": "blocklist",
                    "test_cases": [
                        {
                            "test_case_name": "one_port_blocklisted",
                            "result": "PASS",
                        },
                    ],
                    "summary": {"PASS": 1, "FAIL": 0},
                }
            ]
        }
    ]
}


class TestMain(TestCase):
    def setUp(self):
        self.argv_mock = patch(
            "sys.argv",
            ["run_dpdk_test_suite.py", "--test-suite", "blocklist"],
        ).start()
        self.getenv_mock = patch(
            "run_dpdk_test_suite.os.getenv", return_value="/fake/config.yaml"
        ).start()
        self.is_file_mock = patch(
            "run_dpdk_test_suite.Path.is_file", return_value=True
        ).start()

    def tearDown(self):
        patch.stopall()

    def test_missing_envvar(self):
        """Test that main() fails when DTS_CONFIG_FILE is not set."""
        self.getenv_mock.return_value = None

        with self.assertRaises(SystemExit) as cm:
            main()

        self.assertEqual(
            cm.exception.code,
            "Unable to locate config file for test execution.",
        )

    def test_config_file_not_found(self):
        """Test that dts execution fails when config file does not exist."""
        self.is_file_mock.return_value = False

        with self.assertRaises(SystemExit) as cm:
            main()

        self.assertEqual(
            cm.exception.code,
            "Unable to locate config file for test execution.",
        )

    @patch("run_dpdk_test_suite.DTSRunner.run_test_suite")
    @patch("run_dpdk_test_suite.DTSRunner.print_results", return_value=True)
    def test_dts_successful_run(self, print_mock, run_mock):
        """Test DTS execution with valid config file and environment variables."""
        try:
            main()
        except SystemExit:
            self.fail("main raised SystemExit!")

    @patch(
        "run_dpdk_test_suite.DTSRunner.run_test_suite",
        side_effect=subprocess.CalledProcessError(1, "dpdk-dts"),
    )
    @patch("run_dpdk_test_suite.DTSRunner.print_results", return_value=False)
    def test_subprocess_error(self, print_mock, run_mock):
        """Test that DTS execution subprocess errors are handled gracefully."""
        with self.assertRaises(SystemExit) as cm:
            main()

        self.assertEqual(cm.exception.code, "Test Suite execution failed")
        print_mock.assert_called_once()

    @patch("run_dpdk_test_suite.DTSRunner.run_test_suite")
    @patch("run_dpdk_test_suite.DTSRunner.print_results", return_value=False)
    def test_no_results_found(self, print_mock, run_mock):
        """Test SystemExit raised when no results found."""
        with self.assertRaises(SystemExit) as cm:
            main()

        self.assertEqual(cm.exception.code, "No test results found")


class TestDTSRunnerRunTestSuite(TestCase):
    def setUp(self):
        self.runner = DTSRunner(
            test_suite="blocklist",
            config_file=Path("/fake/config.yaml"),
        )
        self.output_dir = DEFAULT_OUTPUT_DIR / "blocklist"

        self.exists_mock = patch(
            "run_dpdk_test_suite.Path.exists", return_value=False
        ).start()
        self.mkdir_mock = patch("run_dpdk_test_suite.Path.mkdir").start()
        self.copy_mock = patch("run_dpdk_test_suite.shutil.copy").start()
        self.subprocess_mock = patch(
            "run_dpdk_test_suite.subprocess.run"
        ).start()

    def tearDown(self):
        patch.stopall()

    @patch("run_dpdk_test_suite.shutil.rmtree")
    def test_output_dir_cleanup(self, rmtree_mock):
        """Test output directory is called for cleanup before test execution."""
        self.exists_mock.return_value = True

        self.runner.run_test_suite(verbose=False)

        rmtree_mock.assert_called_once_with(self.output_dir)
        self.mkdir_mock.assert_called_once_with(parents=True)

    @patch("run_dpdk_test_suite.shutil.rmtree")
    def test_output_dir_no_cleanup_if_missing(self, rmtree_mock):
        """Test rmtree is skipped when output directory does not exist."""
        self.runner.run_test_suite(verbose=False)

        rmtree_mock.assert_not_called()
        self.mkdir_mock.assert_called_once_with(parents=True)

    def test_config_file_copy_to_snap_common(self):
        """Test that config file is called for copy to SNAP_COMMON"""
        self.runner.run_test_suite(verbose=False)

        self.copy_mock.assert_called_once_with(
            Path("/fake/config.yaml"), DPDK_CONFIG_SNAP_PATH
        )

    def test_dts_command_construction(self):
        """Test DTS command is correctly constructed with and without verbose."""
        expected_base_cmd = [
            DPDK_SNAP_BIN,
            "--test-suite",
            "blocklist",
            "--config-file",
            str(DPDK_CONFIG_SNAP_PATH),
            "--output-dir",
            str(self.output_dir),
        ]

        self.runner.run_test_suite(verbose=False)
        self.subprocess_mock.assert_called_with(
            expected_base_cmd, check=True, timeout=DEFAULT_TIMEOUT
        )

        self.runner.run_test_suite(verbose=True)
        self.subprocess_mock.assert_called_with(
            expected_base_cmd + ["--verbose"],
            check=True,
            timeout=DEFAULT_TIMEOUT,
        )

    def test_dts_raises_called_process_error(self):
        """Test that CalledProcessError is raised on DTS execution failure."""
        self.subprocess_mock.side_effect = subprocess.CalledProcessError(
            1, "dpdk-dts"
        )

        with self.assertRaises(subprocess.CalledProcessError):
            self.runner.run_test_suite(verbose=False)

    def test_dts_raises_timeout_error(self):
        """Test that TimeoutExpired is raised on DTS execution timeout."""
        self.subprocess_mock.side_effect = subprocess.TimeoutExpired(
            "dpdk-dts", DEFAULT_TIMEOUT
        )

        with self.assertRaises(subprocess.TimeoutExpired):
            self.runner.run_test_suite(verbose=False)


class TestDTSRunnerGetResults(TestCase):
    def setUp(self):
        self.runner = DTSRunner(
            test_suite="blocklist",
            config_file=Path("/fake/config.yaml"),
        )

    @patch("run_dpdk_test_suite.Path.is_file", return_value=False)
    def test_no_results_found(self, is_file_mock):
        """Test that None is returned when no results file is found."""
        result = self.runner.get_results()

        self.assertIsNone(result)

    @patch("run_dpdk_test_suite.Path.is_file", return_value=True)
    def test_results_valid_json(self, is_file_mock):
        """Test that valid JSON results are correctly parsed and returned."""
        mock_file = mock_open(read_data=json.dumps(DPDK_RESULTS))

        with patch("run_dpdk_test_suite.Path.open", mock_file):
            result = self.runner.get_results()

        self.assertEqual(result, DPDK_RESULTS)

    @patch("run_dpdk_test_suite.Path.is_file", return_value=True)
    def test_results_invalid_json(self, is_file_mock):
        """Test that invalid JSON results returns None and logs an error."""
        mock_file = mock_open(read_data="not valid json{{{}")

        with patch("run_dpdk_test_suite.Path.open", mock_file):
            result = self.runner.get_results()

        self.assertIsNone(result)

    @patch("run_dpdk_test_suite.Path.is_file", return_value=True)
    def test_results_empty_file(self, is_file_mock):
        """Test that an empty results file returns None."""
        mock_file = mock_open(read_data="")

        with patch("run_dpdk_test_suite.Path.open", mock_file):
            result = self.runner.get_results()

        self.assertIsNone(result)


class TestDTSRunnerPrintResults(TestCase):
    def setUp(self):
        self.runner = DTSRunner(
            test_suite="blocklist",
            config_file=Path("/fake/config.yaml"),
        )

    @patch("run_dpdk_test_suite.DTSRunner.get_results", return_value=None)
    def test_print_when_no_results(self, get_results_mock):
        """Test that False is returned when no results are found."""
        result = self.runner.print_results()

        self.assertFalse(result)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_print_valid_results(self, stdout_mock):
        """Test that valid results are printed and True is returned."""
        with patch(
            "run_dpdk_test_suite.DTSRunner.get_results",
            return_value=DPDK_RESULTS,
        ):
            result = self.runner.print_results()

        self.assertTrue(result)
        output = stdout_mock.getvalue()
        self.assertIn("blocklist", output)
        self.assertIn("one_port_blocklisted", output)
        self.assertIn("PASS", output)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_print_malformed_results(self, stdout_mock):
        """Test that malformed results fall back to json.dumps output."""
        malformed = {"unexpected_key": "value"}

        with patch(
            "run_dpdk_test_suite.DTSRunner.get_results",
            return_value=malformed,
        ):
            result = self.runner.print_results()

        self.assertTrue(result)
        output = stdout_mock.getvalue()
        self.assertIn("unexpected_key", output)
