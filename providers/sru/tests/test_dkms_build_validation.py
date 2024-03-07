from packaging.version import Version
import unittest
from unittest.mock import patch, mock_open
import subprocess

from dkms_build_validation import (
    run_command,
    parse_dkms_status,
    parse_version,
    has_dkms_build_errors,
    main,
)


class TestDKMSValidation(unittest.TestCase):

    # Example output of `dkms status`
    dkms_status = (
        "fwts/24.01.00, 6.5.0-15-generic, x86_64: installed\n"
        "fwts/24.01.00, 6.5.0-17-generic, x86_64: installed"
    )

    @patch("dkms_build_validation.subprocess.check_output")
    def test_run_command(self, mock_check_output):
        mock_check_output.return_value = "output"
        result = run_command(["lsb_release", "-r"])
        self.assertEqual(result, "output")
        mock_check_output.assert_called_once_with(
            ["lsb_release", "-r"],
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    @patch("subprocess.check_output")
    def test_run_command_exception(self, mock_check_output):
        # Simulate a CalledProcessError exception
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, ["test_command"]
        )

        # run_command will raise an exception
        with self.assertRaises(SystemExit):
            run_command(["test_command"])

    @patch("dkms_build_validation.run_command")
    def test_parse_dkms_status(self, mock_run_command):

        ubuntu_release = "22.04"
        kernel_info = parse_dkms_status(self.dkms_status, ubuntu_release)
        # Assuming you have a specific expected output for kernel_info
        expected_kernel_info = [
            {"version": "6.5.0-15-generic", "status": "installed"},
            {"version": "6.5.0-17-generic", "status": "installed"},
        ]
        self.assertEqual(kernel_info, expected_kernel_info)

    @patch("dkms_build_validation.run_command")
    def test_parse_dkms_status_old(self, mock_run_command):
        old_dkms_status = (
            "fwts, 24.01.00, 6.5.0-15-generic, x86_64: installed\n"
            "fwts, 24.01.00, 6.5.0-17-generic, x86_64: installed"
        )
        ubuntu_release = "18.04"
        kernel_info = parse_dkms_status(old_dkms_status, ubuntu_release)
        # Assuming you have a specific expected output for kernel_info
        expected_kernel_info = [
            {"version": "6.5.0-15-generic", "status": "installed"},
            {"version": "6.5.0-17-generic", "status": "installed"},
        ]
        self.assertEqual(kernel_info, expected_kernel_info)

        # Test the old format with a newer Ubuntu release
        ubuntu_release = "22.04"
        kernel_info = parse_dkms_status(old_dkms_status, ubuntu_release)
        self.assertNotEqual(kernel_info, expected_kernel_info)

    def test_parse_version(self):
        # Test with a valid version string
        self.assertEqual(
            parse_version("6.5.0-18-generic"), Version("6.5.0.post18")
        )
        # Test with a shorter valid version string
        self.assertEqual(parse_version("6.5.0"), Version("6.5.0"))

        # Test with an different version string
        self.assertNotEqual(
            parse_version("6.5.0-20-generic"), Version("6.5.0.post18")
        )

        # Test with an invalid version string
        with self.assertRaises(SystemExit):
            parse_version("Wrong version string")

    @patch("dkms_build_validation.run_command")
    def test_has_dkms_build_errors(self, mock_run_command):
        kernel_ver_current = "6.5.0-17-generic"

        # Test with a log file that doesn't contain any errors
        data = "Some log message\nSome log message\nSome log message\n"
        with patch("builtins.open", mock_open(read_data=data)):
            self.assertEqual(has_dkms_build_errors(kernel_ver_current), False)

        # Test with a log file that contains errors
        data = (
            "Some log message\n"
            "Bad return status for module build on kernel: 6.5.0-17-generic\n"
            "Some log message\n"
        )
        with patch("builtins.open", mock_open(read_data=data)):
            self.assertEqual(has_dkms_build_errors(kernel_ver_current), True)

    @patch("dkms_build_validation.has_dkms_build_errors")
    @patch("dkms_build_validation.run_command")
    def test_main_different_kernel(self, mock_run_command, mock_has_err):
        # Mock the run_command function to return specific values
        mock_run_command.side_effect = [
            "22.04",  # lsb_release -r
            self.dkms_status,  # dkms_status
            "6.5.0-20-generic",  # uname -r
        ]
        mock_has_err.return_value = False
        self.assertEqual(main(), 1)

    @patch("dkms_build_validation.has_dkms_build_errors")
    @patch("dkms_build_validation.run_command")
    def test_main_different_kernel_count(self, mock_run_command, mock_has_err):
        warn_dkms_status = (
            "fwts/24.01.00, 6.5.0-15-generic, x86_64: installed\n"
            "fwts_2/24.01.00, 6.5.0-15-generic, x86_64: installed\n"
            "fwts/24.01.00, 6.5.0-17-generic, x86_64: installed"
        )
        # Mock the run_command function to return specific values
        mock_run_command.side_effect = [
            "22.04",  # lsb_release -r
            warn_dkms_status,  # dkms_status
            "6.5.0-17-generic",  # uname -r
        ]
        mock_has_err.return_value = False
        # The test still passes with a warning
        self.assertEqual(main(), 0)

    @patch("dkms_build_validation.has_dkms_build_errors")
    @patch("dkms_build_validation.run_command")
    def test_main_fails_with_errors(self, mock_run_command, mock_has_err):
        # Mock the run_command function to return specific values
        mock_run_command.side_effect = [
            "22.04",  # lsb_release -r
            self.dkms_status,  # dkms_status
            "6.5.0-17-generic",  # uname -r
        ]
        mock_has_err.return_value = True
        self.assertEqual(main(), 1)
