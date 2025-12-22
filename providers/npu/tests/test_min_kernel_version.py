#!/usr/bin/env python3
import unittest
import io
import sys
from unittest.mock import patch

import min_kernel_version


class TestParseVersion(unittest.TestCase):
    def test_standard_version(self):
        self.assertEqual(min_kernel_version.parse_version("6.8.0"), (6, 8, 0))

    def test_version_with_suffix(self):
        self.assertEqual(
            min_kernel_version.parse_version("6.8.0-generic"), (6, 8, 0)
        )

    def test_version_with_multiple_parts(self):
        self.assertEqual(
            min_kernel_version.parse_version("4.9.123-rt-10"), (4, 9, 123, 10)
        )

    def test_text_and_numbers(self):
        self.assertEqual(
            min_kernel_version.parse_version("linux-v4.2-rc1"), (4, 2, 1)
        )

    def test_single_number(self):
        self.assertEqual(min_kernel_version.parse_version("6"), (6,))

    def test_empty_string(self):
        self.assertIsNone(min_kernel_version.parse_version(""))

    def test_no_digits(self):
        self.assertIsNone(min_kernel_version.parse_version("abc-def-ghi"))

    def test_none_input(self):
        self.assertIsNone(min_kernel_version.parse_version(None))


class TestMainFunction(unittest.TestCase):
    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="6.8.0")
    @patch("sys.argv", ["min_kernel_version.py", "5.10.0"])
    def test_supported_version(self, mock_platform, mock_stdout):
        min_kernel_version.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "state: supported")

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="6.8.0")
    @patch("sys.argv", ["min_kernel_version.py", "6.8.0"])
    def test_supported_version_equal(self, mock_platform, mock_stdout):
        min_kernel_version.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "state: supported")

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="6.8.0-generic")
    @patch("sys.argv", ["min_kernel_version.py", "6.8"])
    def test_supported_different_lengths(self, mock_platform, mock_stdout):
        min_kernel_version.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "state: supported")

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="6.7.9")
    @patch("sys.argv", ["min_kernel_version.py", "6.8.0"])
    def test_unsupported_version(self, mock_platform, mock_stdout):
        min_kernel_version.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "state: unsupported")

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="6.11")
    @patch("sys.argv", ["min_kernel_version.py", "6.11.1"])
    def test_unsupported_different_lengths(self, mock_platform, mock_stdout):
        min_kernel_version.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "state: unsupported")

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="invalid-kernel-string")
    @patch("sys.argv", ["min_kernel_version.py", "5.10.0"])
    def test_unsupported_parse_fail_current(self, mock_platform, mock_stdout):
        min_kernel_version.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "state: unsupported")

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="6.8.1")
    @patch("sys.argv", ["min_kernel_version.py", "invalid-required-string"])
    def test_unsupported_parse_fail_required(self, mock_platform, mock_stdout):
        min_kernel_version.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "state: unsupported")


if __name__ == "__main__":
    unittest.main()
