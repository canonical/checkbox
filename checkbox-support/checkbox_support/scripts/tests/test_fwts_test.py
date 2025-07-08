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

from tempfile import NamedTemporaryFile
import os
from io import StringIO

from checkbox_support.scripts.fwts_test import print_log, main


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
        """Test that print_log is called when some tests run, some unavailable."""
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

    def tearDown(self):
        try:
            os.unlink(self.logfile.name)
        except OSError:
            pass
