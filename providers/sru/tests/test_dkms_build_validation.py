from packaging.version import Version
import unittest
from unittest.mock import patch, mock_open
import subprocess

from dkms_build_validation import (
    run_command,
    parse_dkms_status,
    parse_version,
    check_kernel_version,
    check_dkms_module_count,
    get_context_lines,
    has_dkms_build_errors,
    main,
)


class TestDKMSValidation(unittest.TestCase):

    # Example output of `dkms status`
    dkms_status = (
        "fwts/24.01.00, 6.5.0-17-generic, x86_64: installed\n"
        "fwts/24.01.00, 6.5.0-15-generic, x86_64: installed"
    )

    sorted_kernel_info = [
        {"version": "6.5.0-15-generic", "status": "installed"},
        {"version": "6.5.0-17-generic", "status": "installed"},
    ]

    @patch("dkms_build_validation.subprocess.check_output")
    def test_run_command(self, mock_check_output):
        mock_check_output.return_value = "output"
        result = run_command(["lsb_release", "-r"])
        self.assertEqual(result, "output")
        mock_check_output.assert_called_once_with(
            ["lsb_release", "-r"],
            stderr=subprocess.STDOUT,
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

    def test_parse_dkms_status(self):
        ubuntu_release = "22.04"
        kernel_info = parse_dkms_status(self.dkms_status, ubuntu_release)
        # Assuming you have a specific expected output for kernel_info
        expected_kernel_info = [
            {"version": "6.5.0-15-generic", "status": "installed"},
            {"version": "6.5.0-17-generic", "status": "installed"},
        ]
        self.assertEqual(kernel_info, expected_kernel_info)

    def test_parse_dkms_status_old(self):
        old_dkms_status = (
            "fwts, 24.01.00, 6.5.0-17-generic, x86_64: installed\n"
            "fwts, 24.01.00, 6.5.0-15-generic, x86_64: installed"
        )
        ubuntu_release = "18.04"
        sorted_kernel_info = parse_dkms_status(old_dkms_status, ubuntu_release)
        # Assuming you have a specific expected output for kernel_info
        expected_kernel_info = [
            {"version": "6.5.0-15-generic", "status": "installed"},
            {"version": "6.5.0-17-generic", "status": "installed"},
        ]
        self.assertEqual(sorted_kernel_info, expected_kernel_info)

        # Test the old format with a newer Ubuntu release
        ubuntu_release = "22.04"
        sorted_kernel_info = parse_dkms_status(old_dkms_status, ubuntu_release)
        self.assertNotEqual(sorted_kernel_info, expected_kernel_info)

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

    def test_check_kernel_version(self):
        # Test with a kernel version that matches the latest one
        self.assertEqual(
            check_kernel_version(
                "6.5.0-17-generic", self.sorted_kernel_info, self.dkms_status
            ),
            0,
        )

        # Test with a kernel version that doesn't match the latest one
        self.assertEqual(
            check_kernel_version(
                "6.5.0-18-generic", self.sorted_kernel_info, self.dkms_status
            ),
            1,
        )

    def test_check_dkms_module_count(self):
        # Test with the same number of modules
        self.assertEqual(
            check_dkms_module_count(self.sorted_kernel_info, self.dkms_status),
            0,
        )

        # Test with a different number of modules
        bad_kernel_info = self.sorted_kernel_info + [
            {"version": "6.5.0-17-generic", "status": "installed"}
        ]
        self.assertEqual(
            check_dkms_module_count(bad_kernel_info, self.dkms_status),
            1,
        )

    def test_get_context_lines(self):
        log = ["L{}".format(i) for i in range(0, 10)]
        line_idx = [0, 4, 5, 9]
        context = 1
        expected_output = ["L0", "L1", "L3", "L4", "L5", "L6", "L8", "L9"]
        self.assertEqual(
            get_context_lines(log, line_idx, context), expected_output
        )

    def test_get_context_lines_zero_context(self):
        log = ["L{}".format(i) for i in range(0, 10)]
        line_idx = [0, 4, 5, 9]
        context = 0
        expected_output = ["L0", "L4", "L5", "L9"]
        self.assertEqual(
            get_context_lines(log, line_idx, context), expected_output
        )

    def test_get_context_lines_zero_context(self):
        log = ["L{}".format(i) for i in range(0, 10)]
        line_idx = [0, 4, 5, 9]
        context = 0
        expected_output = ["L0", "L4", "L5", "L9"]
        self.assertEqual(
            get_context_lines(log, line_idx, context), expected_output
        )

    def test_get_context_lines_big_context(self):
        log = ["L{}".format(i) for i in range(0, 5)]
        line_idx = [0, 4, 5, 9]
        context = 50
        expected_output = ["L0", "L1", "L2", "L3", "L4"]
        self.assertEqual(
            get_context_lines(log, line_idx, context), expected_output
        )

    def test_has_dkms_build_errors(self):
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

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.parse_dkms_status")
    @patch("dkms_build_validation.check_kernel_version")
    @patch("dkms_build_validation.check_dkms_module_count")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main(
        self, mock_err, mock_count, mock_ver, mock_parse, mock_run_command
    ):
        mock_run_command.return_value = "output"
        mock_parse.return_value = []
        mock_ver.return_value = 0
        mock_count.return_value = 0
        mock_err.return_value = 0
        self.assertEqual(main(), 0)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.parse_dkms_status")
    @patch("dkms_build_validation.check_kernel_version")
    @patch("dkms_build_validation.check_dkms_module_count")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_different_kernel_version(
        self, mock_err, mock_count, mock_ver, mock_parse, mock_run_command
    ):
        mock_run_command.return_value = "output"
        mock_parse.return_value = []
        mock_ver.return_value = 1
        mock_count.return_value = 0
        mock_err.return_value = 0
        self.assertEqual(main(), 1)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.parse_dkms_status")
    @patch("dkms_build_validation.check_kernel_version")
    @patch("dkms_build_validation.check_dkms_module_count")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_with_dkms_build_errors(
        self, mock_err, mock_count, mock_ver, mock_parse, mock_run_command
    ):
        mock_run_command.return_value = "output"
        mock_parse.return_value = []
        mock_ver.return_value = 0
        mock_count.return_value = 0
        mock_err.return_value = 1
        self.assertEqual(main(), 1)
