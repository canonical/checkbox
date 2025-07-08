#
# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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

import unittest
from unittest.mock import patch, MagicMock
from subprocess import PIPE

from tempfile import NamedTemporaryFile
import os
from io import StringIO

from checkbox_support.scripts.fwts_test import (
    print_log,
    main,
    filter_available_tests,
    get_available_fwts_tests,
)


class LogPrinterTest(unittest.TestCase):
    def setUp(self):
        self.logfile = NamedTemporaryFile(delete=False)

    @patch("sys.stdout", new_callable=StringIO)
    def test_logfile_with_encoding_error(self, mock_stdout):
        with open(self.logfile.name, "wb") as f:
            f.write(b"Cannot read PCI config for device 0000:00:\xa1")
            f.write(b"<85>)PNP0B00:00\n")
            f.write(b"SKIPPED: Test 2, Could not guess cache type.\n")
        print_log(self.logfile.name)
        self.assertEqual(
            mock_stdout.getvalue(),
            "WARNING: Found bad char in " + self.logfile.name + "\n",
        )
        os.unlink(self.logfile.name)

    def tearDown(self):
        try:
            os.unlink(self.logfile.name)
        except OSError:
            pass


class FilterAvailableTestsTest(unittest.TestCase):
    """Test the filter_available_tests helper function."""

    @patch("checkbox_support.scripts.fwts_test.get_available_fwts_tests")
    def test_filter_available_tests_all_available(self, mock_get_available):
        """Test when all requested tests are available."""
        mock_get_available.return_value = ["acpitests", "version", "mtrr"]
        requested = ["acpitests", "version"]

        available, unavailable = filter_available_tests(requested)

        self.assertEqual(available, ["acpitests", "version"])
        self.assertEqual(unavailable, [])

    @patch("checkbox_support.scripts.fwts_test.get_available_fwts_tests")
    def test_filter_available_tests_some_unavailable(self, mock_get_available):
        """Test when some requested tests are unavailable."""
        mock_get_available.return_value = ["acpitests", "version"]
        requested = ["acpitests", "nonexistent_test", "version"]

        available, unavailable = filter_available_tests(requested)

        self.assertEqual(available, ["acpitests", "version"])
        self.assertEqual(unavailable, ["nonexistent_test"])

    @patch("checkbox_support.scripts.fwts_test.get_available_fwts_tests")
    def test_filter_available_tests_none_available(self, mock_get_available):
        """Test when none of the requested tests are available."""
        mock_get_available.return_value = ["acpitests", "version"]
        requested = ["nonexistent_test1", "nonexistent_test2"]

        available, unavailable = filter_available_tests(requested)

        self.assertEqual(available, [])
        self.assertEqual(
            unavailable, ["nonexistent_test1", "nonexistent_test2"]
        )

    @patch("checkbox_support.scripts.fwts_test.get_available_fwts_tests")
    def test_filter_available_tests_empty_requested(self, mock_get_available):
        """Test with empty requested tests list."""
        mock_get_available.return_value = ["acpitests", "version"]
        requested = []

        available, unavailable = filter_available_tests(requested)

        self.assertEqual(available, [])
        self.assertEqual(unavailable, [])


class ListOptionsTest(unittest.TestCase):
    """Test the updated list options that use filter_available_tests."""

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.filter_available_tests")
    def test_list_option(self, mock_filter, mock_stdout):
        """Test --list option."""
        mock_filter.return_value = (["acpitests", "version"], [])

        with patch("sys.argv", ["fwts_test.py", "--list"]):
            result = main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("acpitests", output)
        self.assertIn("version", output)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.filter_available_tests")
    def test_list_hwe_option(self, mock_filter, mock_stdout):
        """Test --list-hwe option."""
        mock_filter.return_value = (["mtrr", "virt"], ["apicedge"])

        with patch("sys.argv", ["fwts_test.py", "--list-hwe"]):
            result = main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("mtrr", output)
        self.assertIn("virt", output)
        self.assertNotIn("apicedge", output)  # Should not show unavailable

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.filter_available_tests")
    def test_list_qa_option(self, mock_filter, mock_stdout):
        """Test --list-qa option."""
        mock_filter.return_value = (["acpitests", "version"], ["nonexistent"])

        with patch("sys.argv", ["fwts_test.py", "--list-qa"]):
            result = main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("acpitests", output)
        self.assertIn("version", output)
        self.assertNotIn("nonexistent", output)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.filter_available_tests")
    def test_list_server_option(self, mock_filter, mock_stdout):
        """Test --list-server option."""
        mock_filter.return_value = (["acpitests", "version"], ["nonexistent"])

        with patch("sys.argv", ["fwts_test.py", "--list-server"]):
            result = main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("Server Certification Tests:", output)
        self.assertIn("acpitests", output)
        self.assertIn("version", output)
        self.assertNotIn("nonexistent", output)


class MainFunctionTest(unittest.TestCase):
    def setUp(self):
        self.logfile = NamedTemporaryFile(delete=False)
        # Write some test content to the log file
        with open(self.logfile.name, "w") as f:
            f.write("Test log content\n")

    @patch("sys.argv", ["fwts_test.py", "--log", "test.log"])
    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_print_log_called_when_tests_are_run(
        self, mock_popen, mock_stdout
    ):
        """Test that print_log is called when tests are actually run."""
        # Mock Popen to return successful test results
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"PASSED: Test completed successfully",
            None,
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Mock fwts --show-tests to return some available tests
        mock_fwts_process = MagicMock()
        mock_fwts_process.communicate.return_value = (
            b"acpitests\nversion\n",
            None,
        )
        mock_fwts_process.returncode = 0

        # Configure Popen to return different results for different calls
        mock_popen.side_effect = [mock_fwts_process, mock_process]

        # Run main with a test that should be available
        with patch(
            "sys.argv",
            [
                "fwts_test.py",
                "--test",
                "acpitests",
                "--log",
                self.logfile.name,
            ],
        ):
            main()

        # Verify that print_log was called (log content should be in stdout)
        output = mock_stdout.getvalue()
        self.assertIn("Test log content", output)

    @patch("sys.argv", ["fwts_test.py", "--log", "test.log"])
    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_print_log_not_called_when_no_tests_run(
        self, mock_popen, mock_stdout
    ):
        """Test that print_log is NOT called when no tests are run."""
        # Mock fwts --show-tests to return different available tests
        mock_fwts_process = MagicMock()
        mock_fwts_process.communicate.return_value = (b"version\n", None)
        mock_fwts_process.returncode = 0
        mock_popen.return_value = mock_fwts_process

        # Run main with a test that should NOT be available
        with patch(
            "sys.argv",
            [
                "fwts_test.py",
                "--test",
                "nonexistent_test",
                "--log",
                self.logfile.name,
            ],
        ):
            main()

        # Verify that print_log was NOT called (log content not in stdout)
        output = mock_stdout.getvalue()
        self.assertNotIn("Test log content", output)
        # But we should see the unavailable test message
        self.assertIn("Unavailable Tests: 1", output)

    @patch("sys.argv", ["fwts_test.py", "--log", "test.log"])
    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_print_log_called_when_mixed_available_unavailable(
        self, mock_popen, mock_stdout
    ):
        """Test print_log with some tests run, some unavailable."""
        # Mock Popen to return successful test results
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"PASSED: Test completed successfully",
            None,
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Mock fwts --show-tests to return some available tests
        mock_fwts_process = MagicMock()
        mock_fwts_process.communicate.return_value = (
            b"acpitests\nversion\n",
            None,
        )
        mock_fwts_process.returncode = 0

        # Configure Popen to return different results for different calls
        mock_popen.side_effect = [mock_fwts_process, mock_process]

        # Run main with mixed available and unavailable tests
        with patch(
            "sys.argv",
            [
                "fwts_test.py",
                "--test",
                "acpitests",
                "--test",
                "nonexistent_test",
                "--log",
                self.logfile.name,
            ],
        ):
            main()

        # Verify that print_log was called (log content should be in stdout)
        output = mock_stdout.getvalue()
        self.assertIn("Test log content", output)
        # Also verify that unavailable test message appears
        self.assertIn("Unavailable Tests: 1", output)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_hwe_option_extends_requested_tests(self, mock_popen, mock_stdout):
        """Test that --hwe option extends requested_tests with HWE_TESTS."""
        # Mock fwts --show-tests to return some available tests
        mock_fwts_process = MagicMock()
        mock_fwts_process.communicate.return_value = (
            b"acpitests\nversion\nmtrr\nvirt\napicedge\nklog\noops\n",
            None,
        )
        mock_fwts_process.returncode = 0

        # Mock Popen to return successful test results for each test
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"PASSED: Test completed successfully",
            None,
        )
        mock_process.returncode = 0

        # Configure Popen to return different results for different calls
        # First call is for fwts --show-tests, then one for each test in HWE_TESTS
        mock_popen.side_effect = [
            mock_fwts_process,  # fwts --show-tests
            mock_process,  # version
            mock_process,  # mtrr
            mock_process,  # virt
            mock_process,  # apicedge
            mock_process,  # klog
            mock_process,  # oops
        ]

        # Run main with --hwe option
        with patch(
            "sys.argv",
            [
                "fwts_test.py",
                "--hwe",
                "--log",
                self.logfile.name,
            ],
        ):
            main()

        # Verify that print_log was called (log content should be in stdout)
        output = mock_stdout.getvalue()
        self.assertIn("Test log content", output)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_qa_option_extends_requested_tests(self, mock_popen, mock_stdout):
        """Test that --qa option extends requested_tests with QA_TESTS."""
        # Mock fwts --show-tests to return all QA_TESTS
        from checkbox_support.scripts.fwts_test import QA_TESTS

        mock_fwts_process = MagicMock()
        mock_fwts_process.communicate.return_value = (
            ("\n".join(QA_TESTS)).encode(),
            None,
        )
        mock_fwts_process.returncode = 0

        # Mock Popen to return successful test results for each test
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"PASSED: Test completed successfully",
            None,
        )
        mock_process.returncode = 0

        # Provide enough mocks: 1 for fwts --show-tests, then one for each QA_TESTS
        mock_popen.side_effect = [mock_fwts_process] + [mock_process] * len(
            QA_TESTS
        )

        with patch(
            "sys.argv",
            [
                "fwts_test.py",
                "--qa",
                "--log",
                self.logfile.name,
            ],
        ):
            main()

        output = mock_stdout.getvalue()
        self.assertIn("Test log content", output)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_server_option_extends_requested_tests(
        self, mock_popen, mock_stdout
    ):
        """Test that --server option extends requested_tests with SERVER_TESTS."""
        from checkbox_support.scripts.fwts_test import SERVER_TESTS

        mock_fwts_process = MagicMock()
        mock_fwts_process.communicate.return_value = (
            ("\n".join(SERVER_TESTS)).encode(),
            None,
        )
        mock_fwts_process.returncode = 0

        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"PASSED: Test completed successfully",
            None,
        )
        mock_process.returncode = 0

        mock_popen.side_effect = [mock_fwts_process] + [mock_process] * len(
            SERVER_TESTS
        )

        with patch(
            "sys.argv",
            [
                "fwts_test.py",
                "--server",
                "--log",
                self.logfile.name,
            ],
        ):
            main()

        output = mock_stdout.getvalue()
        self.assertIn("Test log content", output)

    def tearDown(self):
        try:
            os.unlink(self.logfile.name)
        except OSError:
            pass


class GetAvailableFwtsTestsTest(unittest.TestCase):
    """Test the get_available_fwts_tests function."""

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_success(self, mock_popen):
        """Test successful retrieval of available FWTS tests."""
        # Mock successful command execution
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"acpitests\nversion\nmtrr\nvirt\n",
            b"",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        # Verify the command was called correctly
        mock_popen.assert_called_once_with(
            "fwts --show-tests", stdout=PIPE, stderr=PIPE, shell=True
        )

        # Verify the result
        self.assertEqual(result, ["acpitests", "version", "mtrr", "virt"])

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_with_section_headers(self, mock_popen):
        """Test parsing output with section headers (lines ending with ':')."""
        # Mock output with section headers that should be ignored
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"ACPI Tests:\nacpitests\nversion\n\nUEFI Tests:\nmtrr\nvirt\n",
            b"",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        self.assertEqual(result, ["acpitests", "version", "mtrr", "virt"])

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_with_empty_lines(self, mock_popen):
        """Test parsing output with empty lines."""
        # Mock output with empty lines that should be ignored
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"acpitests\n\nversion\n\n\nmtrr\n",
            b"",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        self.assertEqual(result, ["acpitests", "version", "mtrr"])

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_with_whitespace(self, mock_popen):
        """Test parsing output with leading/trailing whitespace."""
        # Mock output with whitespace that should be handled
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"  acpitests  \n\tversion\n  mtrr  \n",
            b"",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        self.assertEqual(result, ["acpitests", "version", "mtrr"])

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_with_multiple_words(self, mock_popen):
        """Test parsing output where lines have multiple words (takes first word)."""
        # Mock output with multiple words per line
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"acpitests - ACPI tests\nversion - Version info\n"
            b"mtrr - MTRR tests\n",
            b"",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        self.assertEqual(result, ["acpitests", "version", "mtrr"])

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_removes_duplicates(self, mock_popen):
        """Test that duplicate test names are removed while preserving order."""
        # Mock output with duplicates
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"acpitests\nversion\nacpitests\nmtrr\nversion\n",
            b"",
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        self.assertEqual(result, ["acpitests", "version", "mtrr"])

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_command_failure(self, mock_popen):
        """Test handling of command failure."""
        # Mock command failure
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"",
            b"fwts: command not found",
        )
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        with self.assertRaises(RuntimeError) as context:
            get_available_fwts_tests()

        self.assertIn("FWTS command failed", str(context.exception))
        self.assertIn("fwts: command not found", str(context.exception))

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_empty_output(self, mock_popen):
        """Test handling of empty output."""
        # Mock empty output
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        self.assertEqual(result, [])

    @patch("checkbox_support.scripts.fwts_test.Popen")
    def test_get_available_fwts_tests_only_whitespace(self, mock_popen):
        """Test handling of output with only whitespace."""
        # Mock output with only whitespace
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"   \n\t\n  \n", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = get_available_fwts_tests()

        self.assertEqual(result, [])
