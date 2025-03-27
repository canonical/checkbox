import unittest
from unittest.mock import patch, mock_open
import sys
import os
import subprocess
from ishtp import (
    get_release_version,
    is_module_loaded,
    check_modules,
    check_devices,
)


class TestISHTP(unittest.TestCase):

    @patch("subprocess.check_output", return_value="24.04\n")
    def test_get_release_version(self, mock_subproc):
        self.assertEqual(get_release_version(), 24)

    @patch("subprocess.check_output", return_value="intel_ishtp 123 0\n")
    def test_is_module_loaded(self, mock_subproc):
        self.assertTrue(is_module_loaded("intel_ishtp"))

    @patch("subprocess.check_output", return_value="")
    def test_is_module_not_loaded(self, mock_subproc):
        self.assertFalse(is_module_loaded("intel_ishtp"))

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "lsmod"),
    )
    def test_is_module_loaded_error(self, mock_subproc):
        self.assertFalse(is_module_loaded("intel_ishtp"))

    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=["device1", "device2"])
    def test_check_devices_success(self, mock_listdir, mock_isdir):
        self.assertEqual(check_devices(), 0)

    @patch("os.path.isdir", return_value=False)
    def test_check_devices_no_directory(self, mock_isdir):
        self.assertEqual(check_devices(), 1)

    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=[])
    def test_check_devices_empty_directory(self, mock_listdir, mock_isdir):
        self.assertEqual(check_devices(), 1)

    @patch("ishtp.is_module_loaded", return_value=True)
    @patch("ishtp.get_release_version", return_value=24)
    def test_check_modules_success(self, mock_release, mock_module):
        self.assertEqual(check_modules(), 0)

    @patch("ishtp.is_module_loaded", return_value=False)
    @patch("ishtp.get_release_version", return_value=24)
    def test_check_modules_fail(self, mock_release, mock_module):
        self.assertEqual(check_modules(), 1)


if __name__ == "__main__":
    unittest.main()
