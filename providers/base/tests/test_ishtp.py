import unittest
from unittest.mock import patch, mock_open
import sys
import os
import subprocess
from ishtp import (
    get_module_list,
    check_modules,
    check_devices,
)


class TestISHTP(unittest.TestCase):

    @patch(
        "subprocess.check_output", return_value="module1\nnodule2\nmodule3\n"
    )
    def test_get_module_list(self, mock_subproc):
        self.assertEqual(get_module_list(), ["module1", "nodule2", "module3"])

    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=["device1", "device2"])
    def test_check_devices_success(self, mock_listdir, mock_isdir):
        try:
            check_devices()
        except SystemExit:
            self.fail("check_devices() raised SystemExit unexpectedly!")

    @patch("os.path.isdir", return_value=False)
    def test_check_devices_no_directory(self, mock_isdir):
        with self.assertRaises(SystemExit):
            check_devices()

    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=[])
    def test_check_devices_empty_directory(self, mock_listdir, mock_isdir):
        with self.assertRaises(SystemExit):
            check_devices()

    @patch(
        "ishtp.get_module_list",
        return_value=["intel_ishtp_hid", "intel_ish_ipc", "intel_ishtp"],
    )
    @patch(
        "ishtp.get_release_info",
        return_value={"release": "24.04"},
    )
    def test_check_modules_success_24(self, mock_release, mock_module):
        try:
            check_modules()
        except SystemExit:
            self.fail("check_devices() raised SystemExit unexpectedly!")

    @patch(
        "ishtp.get_module_list",
        return_value=["intel_ishtp_hid", "intel_ish_ipc"],
    )
    @patch(
        "ishtp.get_release_info",
        return_value={"release": "24.04"},
    )
    def test_check_modules_fail_24(self, mock_release, mock_module):
        with self.assertRaises(SystemExit):
            check_devices()

    @patch(
        "ishtp.get_module_list",
        return_value=[
            "intel_ishtp_loader",
            "intel_ishtp_hid",
            "intel_ish_ipc",
            "intel_ishtp",
        ],
    )
    @patch(
        "ishtp.get_release_info",
        return_value={"release": "22.04"},
    )
    def test_check_modules_success_22(self, mock_release, mock_module):
        try:
            check_modules()
        except SystemExit:
            self.fail("check_devices() raised SystemExit unexpectedly!")

    @patch(
        "ishtp.get_module_list",
        return_value=["intel_ishtp_hid", "intel_ish_ipc"],
    )
    @patch(
        "ishtp.get_release_info",
        return_value={"release": "22.04"},
    )
    def test_check_modules_fail_22(self, mock_release, mock_module):
        with self.assertRaises(SystemExit):
            check_devices()


if __name__ == "__main__":
    unittest.main()
