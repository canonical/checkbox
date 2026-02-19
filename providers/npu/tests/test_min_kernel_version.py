#!/usr/bin/env python3
import unittest
import io
from packaging import version
import sys
from unittest.mock import patch

import min_kernel_version


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
        with self.assertRaises(version.InvalidVersion):
            min_kernel_version.main()

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("platform.release", return_value="6.8.1")
    @patch("sys.argv", ["min_kernel_version.py", "invalid-required-string"])
    def test_unsupported_parse_fail_required(self, mock_platform, mock_stdout):
        with self.assertRaises(version.InvalidVersion):
            min_kernel_version.main()


if __name__ == "__main__":
    unittest.main()
