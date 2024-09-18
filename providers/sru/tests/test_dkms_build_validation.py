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

    dkms_status_empty = ""

    dkms_status_added_only = "fwts-efi-runtime-dkms/24.07.00: added"

    # Example output of `dkms status` on machine
    # in which efi_test driver is used rather than
    # fwts dkms driver
    # https://bugs.launchpad.net/fwts/+bug/2066243
    dkms_status_efi_test_driver = (
        "fwts-efi-runtime-dkms/24.07.00: added\n"
        "tp_smapi/0.43, 6.1.0-1028-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.1.0-1032-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.1.0-1033-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.1.0-1034-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.1.0-1035-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.5.0-1020-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.5.0-1022-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.5.0-1023-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.5.0-1024-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.5.0-1026-oem, x86_64: installed\n"
        "tp_smapi/0.43, 6.8.0-40-generic, x86_64: installed"
    )

    dkms_status_with_warning = (
        "fwts-efi-runtime-dkms/22.03.00, 6.0.0-1011-oem, x86_64: installed "
        "(WARNING! Diff between built and installed module!)"
    )

    dkms_status_oem_focal = (
        "fwts-efi-runtime-dkms, 24.07.00, 5.14.0-1042-oem, x86_64: installed\n"
        "fwts-efi-runtime-dkms, 24.07.00, 5.15.0-117-generic, x86_64: installed"
    )

    dkms_status_stock_noble = (
        "fwts-efi-runtime-dkms/24.07.00: added\n"
        "nvidia/550.107.02, 6.8.0-44-generic, x86_64: installed"
    )

    sorted_kernel_info = [
        {"version": "6.5.0-15-generic", "status": "installed"},
        {"version": "6.5.0-17-generic", "status": "installed"},
    ]

    sorted_kernel_info_empty = []

    sorted_kernel_info_added_only = []

    sorted_kernel_info_efi_test_driver = [
        {"version": "6.1.0-1028-oem", "status": "installed"},
        {"version": "6.1.0-1032-oem", "status": "installed"},
        {"version": "6.1.0-1033-oem", "status": "installed"},
        {"version": "6.1.0-1034-oem", "status": "installed"},
        {"version": "6.1.0-1035-oem", "status": "installed"},
        {"version": "6.5.0-1020-oem", "status": "installed"},
        {"version": "6.5.0-1022-oem", "status": "installed"},
        {"version": "6.5.0-1023-oem", "status": "installed"},
        {"version": "6.5.0-1024-oem", "status": "installed"},
        {"version": "6.5.0-1026-oem", "status": "installed"},
        {"version": "6.8.0-40-generic", "status": "installed"},
    ]

    sorted_kernel_info_with_warning = [
        {"version": "6.0.0-1011-oem", "status": "installed"}
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

    def test_parse_dkms_status_empty(self):
        ubuntu_release = "20.04"
        kernel_info = parse_dkms_status(self.dkms_status_empty, ubuntu_release)
        expected_kernel_info = []
        self.assertEqual(kernel_info, expected_kernel_info)

    def test_parse_dkms_status_added_only(self):
        ubuntu_release = "22.04"
        kernel_info = parse_dkms_status(
            self.dkms_status_added_only, ubuntu_release
        )
        expected_kernel_info = []
        self.assertEqual(kernel_info, expected_kernel_info)

    def test_parse_dkms_status_efi_test(self):
        ubuntu_release = "22.04"
        kernel_info = parse_dkms_status(
            self.dkms_status_efi_test_driver, ubuntu_release
        )
        expected_kernel_info = [
            {"version": "6.1.0-1028-oem", "status": "installed"},
            {"version": "6.1.0-1032-oem", "status": "installed"},
            {"version": "6.1.0-1033-oem", "status": "installed"},
            {"version": "6.1.0-1034-oem", "status": "installed"},
            {"version": "6.1.0-1035-oem", "status": "installed"},
            {"version": "6.5.0-1020-oem", "status": "installed"},
            {"version": "6.5.0-1022-oem", "status": "installed"},
            {"version": "6.5.0-1023-oem", "status": "installed"},
            {"version": "6.5.0-1024-oem", "status": "installed"},
            {"version": "6.5.0-1026-oem", "status": "installed"},
            {"version": "6.8.0-40-generic", "status": "installed"},
        ]
        self.assertEqual(kernel_info, expected_kernel_info)

    def test_parse_dkms_status_with_warning(self):
        ubuntu_release = "22.04"
        kernel_info = parse_dkms_status(
            self.dkms_status_with_warning, ubuntu_release
        )
        expected_kernel_info = [
            {"version": "6.0.0-1011-oem", "status": "installed"},
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

    def test_check_kernel_version_efi_test_driver(self):
        self.assertEqual(
            check_kernel_version(
                "6.1.0-1028-oem",
                self.sorted_kernel_info_efi_test_driver,
                self.dkms_status_efi_test_driver,
            ),
            1,
        )

        self.assertEqual(
            check_kernel_version(
                "6.5.0-1023-oem",
                self.sorted_kernel_info_efi_test_driver,
                self.dkms_status_efi_test_driver,
            ),
            1,
        )

        self.assertEqual(
            check_kernel_version(
                "6.8.0-40-generic",
                self.sorted_kernel_info_efi_test_driver,
                self.dkms_status_efi_test_driver,
            ),
            0,
        )

    def test_check_kernel_version_with_warning(self):
        self.assertEqual(
            check_kernel_version(
                "6.0.0-1011-oem",
                self.sorted_kernel_info_with_warning,
                self.dkms_status_with_warning,
            ),
            0,
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

    def test_get_context_lines_center(self):
        log = ["L{}".format(i) for i in range(0, 20)]
        line_idx = {10, 11}
        expected_output = ["L{}".format(i) for i in range(5, 17)]
        self.assertEqual(get_context_lines(log, line_idx), expected_output)

    def test_get_context_lines_edges(self):
        log = ["L{}".format(i) for i in range(0, 20)]
        line_idx = {0, 18}
        expected_output = [
            "L0",
            "L1",
            "L2",
            "L3",
            "L4",
            "L5",
            "L13",
            "L14",
            "L15",
            "L16",
            "L17",
            "L18",
            "L19",
        ]
        self.assertEqual(get_context_lines(log, line_idx), expected_output)

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
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main(self, mock_err, mock_run_command):
        # 0: lsb_release -r
        # 1: dkms status
        # 2: uname -r
        mock_run_command.side_effect = [
            "Release:	22.04",
            self.dkms_status,
            "6.5.0-17-generic",
        ]
        mock_err.return_value = 0
        result = main()
        self.assertEqual(mock_err.call_count, 1)
        self.assertEqual(result, 0)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_empty(self, mock_err, mock_run_command):
        mock_run_command.side_effect = [
            "Release:	22.04",
            "",
            "6.8.0-40-generic",
        ]
        mock_err.return_value = 0
        result = main()
        self.assertEqual(mock_err.call_count, 0)
        self.assertEqual(result, 0)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_added_only(self, mock_err, mock_run_command):
        mock_run_command.side_effect = [
            "Release:	22.04",
            self.dkms_status_added_only,
            "6.8.0-40-generic",
        ]
        mock_err.return_value = 0
        result = main()
        self.assertEqual(mock_err.call_count, 0)
        self.assertEqual(result, 0)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_efi_test_driver(self, mock_err, mock_run_command):
        mock_run_command.side_effect = [
            "Release:	22.04",
            self.dkms_status_efi_test_driver,
            "6.8.0-40-generic",
        ]
        mock_err.return_value = 0
        result = main()
        self.assertEqual(mock_err.call_count, 1)
        self.assertEqual(result, 0)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_with_warning(self, mock_err, mock_run_command):
        mock_run_command.side_effect = [
            "Release:	22.04",
            self.dkms_status_with_warning,
            "6.0.0-1011-oem",
        ]
        mock_err.return_value = 0
        result = main()
        self.assertEqual(mock_err.call_count, 1)
        self.assertEqual(result, 0)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_with_dkms_build_errors(self, mock_err, mock_run_command):
        mock_run_command.side_effect = [
            "Release:	22.04",
            self.dkms_status,
            "6.5.0-17-generic",
        ]
        mock_err.return_value = 1
        result = main()
        self.assertEqual(mock_err.call_count, 1)
        self.assertEqual(result, 1)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_oem_focal(self, mock_err, mock_run_command):
        mock_run_command.side_effect = [
            "Release:	20.04",
            self.dkms_status_oem_focal,
            "5.15.0-117-generic",
        ]
        mock_err.return_value = 0
        result = main()
        self.assertEqual(mock_err.call_count, 1)
        self.assertEqual(result, 0)

    @patch("dkms_build_validation.run_command")
    @patch("dkms_build_validation.has_dkms_build_errors")
    def test_main_stock_noble(self, mock_err, mock_run_command):
        mock_run_command.side_effect = [
            "No LSB modules are available.\nRelease:	24.04",
            self.dkms_status_stock_noble,
            "6.8.0-44-generic",
        ]
        mock_err.return_value = 0
        result = main()
        self.assertEqual(mock_err.call_count, 1)
        self.assertEqual(result, 0)
