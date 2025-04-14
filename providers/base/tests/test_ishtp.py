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
        self.assertEqual(check_devices(), 0)

    @patch("os.path.isdir", return_value=False)
    def test_check_devices_no_directory(self, mock_isdir):
        self.assertRaises(SystemExit)

    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=[])
    def test_check_devices_empty_directory(self, mock_listdir, mock_isdir):
        self.assertRaises(SystemExit)

    @patch(
        "ishtp.get_module_list",
        return_value=["intel_ishtp_hid", "intel_ish_ipc", "intel_ishtp"],
    )
    @patch(
        "checkbox_support.helpers.release_info.get_release_info",
        return_value="24.04",
    )
    def test_check_modules_success_24(self, mock_release, mock_module):
        self.assertEqual(check_modules(), 0)

    @patch(
        "ishtp.get_module_list",
        return_value=["intel_ishtp_hid", "intel_ish_ipc"],
    )
    @patch(
        "checkbox_support.helpers.release_info.get_release_info",
        return_value="24.04",
    )
    def test_check_modules_fail_24(self, mock_release, mock_module):
        self.assertRaises(SystemExit)

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
        "checkbox_support.helpers.release_info.get_release_info",
        return_value="22.04",
    )
    def test_check_modules_success_22(self, mock_release, mock_module):
        self.assertEqual(check_modules(), 0)

    @patch(
        "ishtp.get_module_list",
        return_value=["intel_ishtp_hid", "intel_ish_ipc"],
    )
    @patch(
        "checkbox_support.helpers.release_info.get_release_info",
        return_value="22.04",
    )
    def test_check_modules_fail_22(self, mock_release, mock_module):
        self.assertRaises(SystemExit)


if __name__ == "__main__":
    unittest.main()
