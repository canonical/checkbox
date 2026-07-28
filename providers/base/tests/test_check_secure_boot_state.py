#!/usr/bin/env python3
"""Unit tests for check_secure_boot_state.py"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

import check_secure_boot_state

DUMPIMAGE_SIGNED = """FIT description: U-Boot fitImage for kernel
Created:         Thu Jan  1 00:00:00 2026
 Image 0 (kernel-1)
  Description:  Linux kernel
  Type:         Kernel Image
  Compression:  gzip compressed
  Data Size:    8388608 Bytes = 8192.00 KiB = 8.00 MiB
  Architecture: AArch64
  OS:           Linux
  Load Address: 0x40080000
  Entry Point:  0x40080000
  Hash algo:    sha256
  Hash value:   0123456789abcdef
 Default Configuration: 'conf-1'
 Configuration 0 (conf-1)
  Description:  Boot Linux kernel with FDT blob
  Kernel:       kernel-1
  Sign algo:    sha256,rsa2048:dev
  Sign value:   aabbccddeeff0011
"""

DUMPIMAGE_UNSIGNED = """FIT description: U-Boot fitImage for kernel
Created:         Thu Jan  1 00:00:00 2026
 Image 0 (kernel-1)
  Description:  Linux kernel
  Type:         Kernel Image
  Architecture: AArch64
  OS:           Linux
  Hash algo:    sha256
  Hash value:   0123456789abcdef
 Default Configuration: 'conf-1'
 Configuration 0 (conf-1)
  Description:  Boot Linux kernel with FDT blob
  Kernel:       kernel-1
"""


def make_path(is_dir=False, is_file=False, data=None, error=None):
    path = MagicMock()
    path.is_dir.return_value = is_dir
    path.is_file.return_value = is_file
    if error is not None:
        path.read_bytes.side_effect = error
    else:
        path.read_bytes.return_value = data
    return path


def patch_paths(mapping):
    """Patch Path() so each known path string gets its configured mock."""
    return patch(
        "check_secure_boot_state.Path", side_effect=lambda p: mapping[p]
    )


class TestGetUefiState(unittest.TestCase):
    def run_with(self, var_path):
        mapping = {
            check_secure_boot_state.EFIVARS_DIR: make_path(is_dir=True),
            check_secure_boot_state.SECUREBOOT_VAR: var_path,
        }
        with patch_paths(mapping):
            return check_secure_boot_state.get_uefi_state()

    def test_enabled(self):
        var = make_path(is_file=True, data=b"\x06\x00\x00\x00\x01")
        self.assertEqual(self.run_with(var), "enabled")

    def test_disabled(self):
        var = make_path(is_file=True, data=b"\x06\x00\x00\x00\x00")
        self.assertEqual(self.run_with(var), "disabled")

    def test_variable_missing_means_disabled(self):
        var = make_path(is_file=False)
        self.assertEqual(self.run_with(var), "disabled")

    def test_unreadable_variable_raises(self):
        var = make_path(is_file=True, error=OSError("denied"))
        with self.assertRaises(SystemExit):
            self.run_with(var)

    def test_short_variable_raises(self):
        var = make_path(is_file=True, data=b"\x06\x00")
        with self.assertRaises(SystemExit):
            self.run_with(var)

    def test_efivars_missing_raises(self):
        mapping = {
            check_secure_boot_state.EFIVARS_DIR: make_path(is_dir=False)
        }
        with patch_paths(mapping):
            with self.assertRaises(SystemExit):
                check_secure_boot_state.get_uefi_state()


@patch("check_secure_boot_state.add_hostfs_prefix", side_effect=lambda p: p)
class TestFindFitImage(unittest.TestCase):
    @patch("check_secure_boot_state.Path")
    @patch("check_secure_boot_state.get_kernel_snap", return_value="pi")
    @patch("check_secure_boot_state.on_ubuntucore", return_value=True)
    def test_kernel_snap_image(self, _core, _snap, mock_path, _prefix):
        mock_path.return_value.is_file.return_value = True
        self.assertEqual(
            check_secure_boot_state.find_fit_image(),
            "/snap/pi/current/kernel.img",
        )

    @patch("check_secure_boot_state.glob.glob")
    @patch("check_secure_boot_state.get_kernel_snap", return_value=None)
    @patch("check_secure_boot_state.on_ubuntucore", return_value=True)
    def test_core_without_kernel_snap_falls_back(
        self, _core, _snap, mock_glob, _prefix
    ):
        mock_glob.side_effect = lambda p: (
            ["/boot/board.itb"] if p == "/boot/*.itb" else []
        )
        self.assertEqual(
            check_secure_boot_state.find_fit_image(), "/boot/board.itb"
        )

    @patch("check_secure_boot_state.glob.glob")
    @patch("check_secure_boot_state.on_ubuntucore", return_value=False)
    def test_classic_returns_first_sorted_match(
        self, _core, mock_glob, _prefix
    ):
        mock_glob.side_effect = lambda p: (
            ["/boot/b.itb", "/boot/a.itb"] if p == "/boot/*.itb" else []
        )
        self.assertEqual(
            check_secure_boot_state.find_fit_image(), "/boot/a.itb"
        )

    @patch("check_secure_boot_state.glob.glob", return_value=[])
    @patch("check_secure_boot_state.on_ubuntucore", return_value=False)
    def test_no_image_returns_none(self, _core, _glob, _prefix):
        self.assertIsNone(check_secure_boot_state.find_fit_image())


@patch("check_secure_boot_state.subprocess.check_output")
class TestGetFitState(unittest.TestCase):
    def test_signed_image_is_enabled(self, mock_output):
        mock_output.return_value = DUMPIMAGE_SIGNED
        self.assertEqual(
            check_secure_boot_state.get_fit_state("/boot/a.itb"), "enabled"
        )
        mock_output.assert_called_with(
            ["dumpimage", "-l", "/boot/a.itb"],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=30,
        )

    def test_unsigned_image_is_disabled(self, mock_output):
        mock_output.return_value = DUMPIMAGE_UNSIGNED
        self.assertEqual(
            check_secure_boot_state.get_fit_state("/boot/a.itb"),
            "disabled",
        )

    def test_missing_dumpimage_raises(self, mock_output):
        mock_output.side_effect = FileNotFoundError()
        with self.assertRaises(SystemExit) as ctx:
            check_secure_boot_state.get_fit_state("/boot/a.itb")
        self.assertIn("u-boot-tools", str(ctx.exception))

    def test_dumpimage_failure_raises(self, mock_output):
        mock_output.side_effect = subprocess.CalledProcessError(
            1, "dumpimage", output="bad"
        )
        with self.assertRaises(SystemExit):
            check_secure_boot_state.get_fit_state("/boot/a.itb")

    def test_dumpimage_timeout_raises(self, mock_output):
        mock_output.side_effect = subprocess.TimeoutExpired("dumpimage", 30)
        with self.assertRaises(SystemExit):
            check_secure_boot_state.get_fit_state("/boot/a.itb")

    def test_non_fit_output_raises(self, mock_output):
        mock_output.return_value = "GP Header: Size 20000 LoadAddr 402\n"
        with self.assertRaises(SystemExit) as ctx:
            check_secure_boot_state.get_fit_state("/boot/a.itb")
        self.assertIn("not a FIT image", str(ctx.exception))


class TestGetSecureBootState(unittest.TestCase):
    @patch("check_secure_boot_state.get_uefi_state", return_value="enabled")
    @patch("check_secure_boot_state.Path")
    def test_auto_prefers_secureboot_variable(self, mock_path, mock_uefi):
        mock_path.return_value.is_file.return_value = True
        self.assertEqual(
            check_secure_boot_state.get_secure_boot_state(), "enabled"
        )
        self.assertEqual(mock_uefi.call_count, 1)

    @patch("check_secure_boot_state.get_fit_state", return_value="disabled")
    @patch(
        "check_secure_boot_state.find_fit_image",
        return_value="/boot/a.itb",
    )
    @patch("check_secure_boot_state.Path")
    def test_auto_falls_back_to_fit(self, mock_path, mock_find, mock_fit):
        mock_path.return_value.is_file.return_value = False
        self.assertEqual(
            check_secure_boot_state.get_secure_boot_state(), "disabled"
        )
        mock_fit.assert_called_with("/boot/a.itb")

    @patch("check_secure_boot_state.get_uefi_state", return_value="disabled")
    @patch("check_secure_boot_state.find_fit_image", return_value=None)
    @patch("check_secure_boot_state.Path")
    def test_auto_efi_without_variable_or_fit(
        self, mock_path, _find, mock_uefi
    ):
        mock_path.return_value.is_file.return_value = False
        mock_path.return_value.is_dir.return_value = True
        self.assertEqual(
            check_secure_boot_state.get_secure_boot_state(), "disabled"
        )
        self.assertEqual(mock_uefi.call_count, 1)

    @patch("check_secure_boot_state.find_fit_image", return_value=None)
    @patch("check_secure_boot_state.Path")
    def test_auto_nothing_found_raises(self, mock_path, _find):
        mock_path.return_value.is_file.return_value = False
        mock_path.return_value.is_dir.return_value = False
        with self.assertRaises(SystemExit) as ctx:
            check_secure_boot_state.get_secure_boot_state()
        self.assertIn("Cannot determine", str(ctx.exception))

    @patch("check_secure_boot_state.get_uefi_state", return_value="enabled")
    def test_method_uefi_forced(self, mock_uefi):
        self.assertEqual(
            check_secure_boot_state.get_secure_boot_state("uefi"),
            "enabled",
        )
        self.assertEqual(mock_uefi.call_count, 1)

    @patch("check_secure_boot_state.get_fit_state", return_value="enabled")
    @patch(
        "check_secure_boot_state.find_fit_image",
        return_value="/boot/a.itb",
    )
    def test_method_fit_forced(self, _find, mock_fit):
        self.assertEqual(
            check_secure_boot_state.get_secure_boot_state("fit"), "enabled"
        )
        mock_fit.assert_called_with("/boot/a.itb")

    @patch("check_secure_boot_state.find_fit_image", return_value=None)
    def test_method_fit_without_image_raises(self, _find):
        with self.assertRaises(SystemExit) as ctx:
            check_secure_boot_state.get_secure_boot_state("fit")
        self.assertIn("No FIT kernel image found", str(ctx.exception))


class TestMain(unittest.TestCase):
    @patch("builtins.print")
    @patch(
        "check_secure_boot_state.get_secure_boot_state",
        return_value="enabled",
    )
    def test_expected_state_passes(self, _state, mock_print):
        self.assertEqual(check_secure_boot_state.main(["enabled"]), 0)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("PASS", printed)

    @patch("builtins.print")
    @patch(
        "check_secure_boot_state.get_secure_boot_state",
        return_value="enabled",
    )
    def test_unexpected_state_fails(self, _state, _print):
        with self.assertRaises(SystemExit) as ctx:
            check_secure_boot_state.main(["disabled"])
        self.assertIn("disabled", str(ctx.exception))
        self.assertIn("enabled", str(ctx.exception))

    @patch("builtins.print")
    @patch(
        "check_secure_boot_state.get_secure_boot_state",
        return_value="enabled",
    )
    def test_method_from_environment(self, mock_state, _print):
        env = {"SECURE_BOOT_CHECK_METHOD": "fit"}
        with patch.dict("os.environ", env):
            check_secure_boot_state.main(["enabled"])
        mock_state.assert_called_with("fit")

    @patch("builtins.print")
    @patch(
        "check_secure_boot_state.get_secure_boot_state",
        return_value="enabled",
    )
    def test_method_flag_overrides_environment(self, mock_state, _print):
        env = {"SECURE_BOOT_CHECK_METHOD": "fit"}
        with patch.dict("os.environ", env):
            check_secure_boot_state.main(["enabled", "--method", "uefi"])
        mock_state.assert_called_with("uefi")

    def test_invalid_method_from_environment(self):
        env = {"SECURE_BOOT_CHECK_METHOD": "bogus"}
        with patch.dict("os.environ", env):
            with self.assertRaises(SystemExit) as ctx:
                check_secure_boot_state.main(["enabled"])
        self.assertIn("Invalid SECURE_BOOT_CHECK_METHOD", str(ctx.exception))


class TestArgumentParser(unittest.TestCase):
    def test_parses_expected_and_verbose(self):
        args = check_secure_boot_state.parse_args(["enabled", "--verbose"])
        self.assertEqual(args.expected, "enabled")
        self.assertTrue(args.verbose)
        self.assertIsNone(args.method)

    def test_parses_method(self):
        args = check_secure_boot_state.parse_args(
            ["disabled", "--method", "fit"]
        )
        self.assertEqual(args.method, "fit")

    @patch("sys.stderr")
    def test_invalid_method_rejected(self, _stderr):
        with self.assertRaises(SystemExit):
            check_secure_boot_state.parse_args(
                ["enabled", "--method", "bogus"]
            )

    @patch("sys.stderr")
    def test_invalid_state_rejected(self, _stderr):
        with self.assertRaises(SystemExit):
            check_secure_boot_state.parse_args(["on"])


if __name__ == "__main__":
    unittest.main()
