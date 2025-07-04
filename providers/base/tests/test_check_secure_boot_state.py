#!/usr/bin/env python3
"""
Unit tests for check_secure_boot_state.py

This module provides comprehensive test coverage for the secure boot state
checking functionality, including all classes, methods, and edge cases.
"""

import os
import sys
import unittest
import argparse
import subprocess
from unittest.mock import Mock, patch, mock_open

# Add the bin directory to the path so we can import the script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

# Import after path modification
from check_secure_boot_state import (  # noqa: E402
    SecureBootLogger,
    SecureBootState,
    SecureBootError,
    SecureBootProcessingError,
    SecureBootNotSupportedError,
    SecureBootConfigurationError,
    UbuntuVariant,
    CheckerType,
    SecureBootChecker,
    UEFISecureBootChecker,
    FITImageSecureBootChecker,
    log_secure_boot_info,
    check_secure_boot_result,
    create_checker,
    create_parser,
    main,
)


class TestSecureBootLogger(unittest.TestCase):
    """Test cases for SecureBootLogger class."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = SecureBootLogger(verbose=True)

    @patch("logging.debug")
    def test_debug_with_args(self, mock_debug):
        """Test debug logging with arguments."""
        self.logger.debug("Test message {}", "arg")
        mock_debug.assert_called_once_with("Test message arg")

    @patch("logging.debug")
    def test_debug_without_args(self, mock_debug):
        """Test debug logging without arguments."""
        self.logger.debug("Test message")
        mock_debug.assert_called_once_with("Test message")

    @patch("logging.info")
    def test_info_with_args(self, mock_info):
        """Test info logging with arguments."""
        self.logger.info("Test message {}", "arg")
        mock_info.assert_called_once_with("Test message arg")

    @patch("logging.warning")
    def test_warning_with_args(self, mock_warning):
        """Test warning logging with arguments."""
        self.logger.warning("Test message {}", "arg")
        mock_warning.assert_called_once_with("Test message arg")

    @patch("logging.error")
    def test_error_with_args(self, mock_error):
        """Test error logging with arguments."""
        self.logger.error("Test message {}", "arg")
        mock_error.assert_called_once_with("Test message arg")

    @patch("logging.error")
    def test_log_failure_with_error_msg(self, mock_error):
        """Test log_failure with error message."""
        self.logger.log_failure("enabled", "disabled", "test error")
        mock_error.assert_called_once_with(
            "FAIL: Secure boot is not enabled - test error"
        )

    @patch("logging.error")
    def test_log_failure_without_error_msg(self, mock_error):
        """Test log_failure without error message."""
        self.logger.log_failure("enabled", "disabled", None)
        mock_error.assert_called_once_with(
            "FAIL: Secure boot is not enabled (current state: disabled)"
        )

    @patch("logging.info")
    def test_info_without_args(self, mock_info):
        """Test info logging without arguments."""
        self.logger.info("Test message")
        mock_info.assert_called_once_with("Test message")

    @patch("logging.warning")
    def test_warning_without_args(self, mock_warning):
        """Test warning logging without arguments."""
        self.logger.warning("Test message")
        mock_warning.assert_called_once_with("Test message")

    @patch("logging.error")
    def test_error_without_args(self, mock_error):
        """Test error logging without arguments."""
        self.logger.error("Test message")
        mock_error.assert_called_once_with("Test message")


class TestEnums(unittest.TestCase):
    """Test cases for enum classes."""

    def test_secure_boot_state_enum(self):
        """Test SecureBootState enum values."""
        self.assertEqual(SecureBootState.ENABLED.value, "enabled")
        self.assertEqual(SecureBootState.DISABLED.value, "disabled")
        self.assertEqual(SecureBootState.NOT_SUPPORTED.value, "not_supported")
        self.assertEqual(
            SecureBootState.NO_IMAGES_FOUND.value, "no_images_found"
        )
        self.assertEqual(
            SecureBootState.PROCESSING_ERROR.value, "processing_error"
        )
        self.assertEqual(
            SecureBootState.UNEXPECTED_OUTPUT.value, "unexpected_output"
        )

    def test_ubuntu_variant_enum(self):
        """Test UbuntuVariant enum values."""
        self.assertEqual(UbuntuVariant.CORE.value, "core")
        self.assertEqual(UbuntuVariant.CLASSIC.value, "classic")
        self.assertEqual(UbuntuVariant.UNKNOWN.value, "unknown")

    def test_checker_type_enum(self):
        """Test CheckerType enum values."""
        self.assertEqual(CheckerType.UEFI.value, "uefi")
        self.assertEqual(CheckerType.FIT.value, "fit")
        self.assertEqual(CheckerType.AUTO.value, "auto")


class TestExceptions(unittest.TestCase):
    """Test cases for exception classes."""

    def test_secure_boot_error_inheritance(self):
        """Test SecureBootError inheritance."""
        error = SecureBootError("test message")
        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), "test message")

    def test_secure_boot_processing_error_inheritance(self):
        """Test SecureBootProcessingError inheritance."""
        error = SecureBootProcessingError("test message")
        self.assertIsInstance(error, SecureBootError)
        self.assertEqual(str(error), "test message")

    def test_secure_boot_not_supported_error_inheritance(self):
        """Test SecureBootNotSupportedError inheritance."""
        error = SecureBootNotSupportedError("test message")
        self.assertIsInstance(error, SecureBootError)
        self.assertEqual(str(error), "test message")

    def test_secure_boot_configuration_error_inheritance(self):
        """Test SecureBootConfigurationError inheritance."""
        error = SecureBootConfigurationError("test message")
        self.assertIsInstance(error, SecureBootError)
        self.assertEqual(str(error), "test message")


class TestSecureBootChecker(unittest.TestCase):
    """Test cases for SecureBootChecker base class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock logger and set it as the global logger
        self.mock_logger = Mock(spec=SecureBootLogger)

        # Import the module and set the global logger
        import check_secure_boot_state

        check_secure_boot_state.logger = self.mock_logger

        # Create a concrete implementation for testing
        class TestChecker(SecureBootChecker):
            def get_secure_boot_state(self):
                return (SecureBootState.ENABLED, None)

            def is_supported(self):
                return True

        self.checker = TestChecker()

    @patch.dict(os.environ, {"SNAP": "/snap/test/1"})
    def test_get_hostfs_prefix_with_snap(self):
        """Test hostfs prefix when running in snap environment."""
        prefix = self.checker._get_hostfs_prefix()
        self.assertEqual(prefix, "/var/lib/snapd/hostfs")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_hostfs_prefix_without_snap(self):
        """Test hostfs prefix when not running in snap environment."""
        prefix = self.checker._get_hostfs_prefix()
        self.assertEqual(prefix, "")

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_detect_ubuntu_variant_core(self, mock_run):
        """Test Ubuntu variant detection for Core."""
        mock_run.return_value = (0, "Ubuntu Core 22", "")
        variant = self.checker._detect_ubuntu_variant()
        self.assertEqual(variant, UbuntuVariant.CORE)

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_detect_ubuntu_variant_classic(self, mock_run):
        """Test Ubuntu variant detection for Classic."""
        mock_run.return_value = (0, "Ubuntu 22.04.3 LTS", "")
        variant = self.checker._detect_ubuntu_variant()
        self.assertEqual(variant, UbuntuVariant.CLASSIC)

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_detect_ubuntu_variant_unknown(self, mock_run):
        """Test Ubuntu variant detection for unknown OS."""
        mock_run.return_value = (0, "Debian GNU/Linux", "")
        variant = self.checker._detect_ubuntu_variant()
        self.assertEqual(variant, UbuntuVariant.UNKNOWN)

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_detect_ubuntu_variant_failure(self, mock_run):
        """Test Ubuntu variant detection when command fails."""
        mock_run.return_value = (1, "", "error")
        variant = self.checker._detect_ubuntu_variant()
        self.assertEqual(variant, UbuntuVariant.UNKNOWN)

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_detect_ubuntu_variant_exception(self, mock_run):
        """Test Ubuntu variant detection when exception occurs."""
        mock_run.side_effect = Exception("test error")
        variant = self.checker._detect_ubuntu_variant()
        self.assertEqual(variant, UbuntuVariant.UNKNOWN)

    def test_build_search_patterns_with_hostfs(self):
        """Test search pattern building with hostfs prefix."""
        self.checker.hostfs_prefix = "/var/lib/snapd/hostfs"
        base_patterns = ["/boot/*.img", "/boot/*.dtb"]
        patterns = self.checker._build_search_patterns(base_patterns)
        expected = [
            "/var/lib/snapd/hostfs/boot/*.img",
            "/var/lib/snapd/hostfs/boot/*.dtb",
            "/boot/*.img",
            "/boot/*.dtb",
        ]
        self.assertEqual(patterns, expected)

    def test_build_search_patterns_without_hostfs(self):
        """Test search pattern building without hostfs prefix."""
        self.checker.hostfs_prefix = ""
        base_patterns = ["/boot/*.img", "/boot/*.dtb"]
        patterns = self.checker._build_search_patterns(base_patterns)
        self.assertEqual(patterns, base_patterns)

    @patch("glob.glob")
    def test_find_files_by_patterns(self, mock_glob):
        """Test file finding by patterns."""
        mock_glob.side_effect = [
            ["/boot/test1.img", "/boot/test2.img"],
            ["/boot/test2.img", "/boot/test3.img"],  # Duplicate
        ]
        patterns = ["/boot/*.img", "/boot/*.dtb"]
        files = self.checker._find_files_by_patterns(patterns)
        expected = ["/boot/test1.img", "/boot/test2.img", "/boot/test3.img"]
        self.assertEqual(files, expected)

    @patch("glob.glob")
    def test_find_files_by_patterns_with_exception(self, mock_glob):
        """Test file finding by patterns with exception."""
        mock_glob.side_effect = [["/boot/test1.img"], Exception("test error")]
        patterns = ["/boot/*.img", "/boot/*.dtb"]
        files = self.checker._find_files_by_patterns(patterns)
        self.assertEqual(files, ["/boot/test1.img"])

    @patch("subprocess.Popen")
    def test_run_command_with_timeout_success(self, mock_popen):
        """Test command execution with timeout - success case."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("stdout", "stderr")
        mock_popen.return_value = mock_process

        return_code, stdout, stderr = self.checker._run_command_with_timeout(
            ["test"]
        )
        self.assertEqual(return_code, 0)
        self.assertEqual(stdout, "stdout")
        self.assertEqual(stderr, "stderr")

    @patch("subprocess.Popen")
    def test_run_command_with_timeout_timeout(self, mock_popen):
        """Test command execution with timeout - timeout case."""
        mock_process = Mock()
        mock_process.communicate.side_effect = [
            subprocess.TimeoutExpired("test", 10),
            ("", ""),
        ]
        mock_popen.return_value = mock_process

        return_code, stdout, stderr = self.checker._run_command_with_timeout(
            ["test"]
        )
        self.assertEqual(return_code, -1)
        self.assertIn("timed out", stderr)

    @patch("subprocess.Popen")
    def test_run_command_with_timeout_oserror(self, mock_popen):
        """Test command execution with timeout - OSError case."""
        mock_popen.side_effect = OSError("command not found")

        return_code, stdout, stderr = self.checker._run_command_with_timeout(
            ["test"]
        )
        self.assertEqual(return_code, -1)
        self.assertIn("not found", stderr)

    @patch("subprocess.Popen")
    def test_run_command_with_timeout_exception(self, mock_popen):
        """Test command execution with timeout - general exception case."""
        mock_popen.side_effect = Exception("test error")

        return_code, stdout, stderr = self.checker._run_command_with_timeout(
            ["test"]
        )
        self.assertEqual(return_code, -1)
        self.assertIn("Subprocess error", stderr)


class TestUEFISecureBootChecker(unittest.TestCase):
    """Test cases for UEFISecureBootChecker class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock logger and set it as the global logger
        self.mock_logger = Mock(spec=SecureBootLogger)

        # Import the module and set the global logger
        import check_secure_boot_state

        check_secure_boot_state.logger = self.mock_logger

        self.checker = UEFISecureBootChecker()

    @patch("os.path.isdir")
    def test_is_supported_true(self, mock_isdir):
        """Test UEFI support detection - supported."""
        mock_isdir.return_value = True
        self.assertTrue(UEFISecureBootChecker.is_supported())

    @patch("os.path.isdir")
    def test_is_supported_false(self, mock_isdir):
        """Test UEFI support detection - not supported."""
        mock_isdir.return_value = False
        self.assertFalse(UEFISecureBootChecker.is_supported())

    @patch("os.path.isdir")
    @patch("shutil.which")
    def test_get_secure_boot_state_not_supported(self, mock_which, mock_isdir):
        """Test secure boot state when UEFI not supported."""
        mock_isdir.return_value = False
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.NOT_SUPPORTED)
        self.assertIn("no /sys/firmware/efi directory", error_msg)

    @patch("os.path.isdir")
    @patch("shutil.which")
    def test_get_secure_boot_state_no_mokutil(self, mock_which, mock_isdir):
        """Test secure boot state when mokutil not available."""
        mock_isdir.return_value = True
        mock_which.return_value = None
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.NOT_SUPPORTED)
        self.assertIn("mokutil command not found", error_msg)

    @patch("os.path.isdir")
    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_get_secure_boot_state_enabled(
        self, mock_run, mock_which, mock_isdir
    ):
        """Test secure boot state - enabled."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/mokutil"
        mock_run.return_value = (0, "SecureBoot enabled", "")
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.ENABLED)
        self.assertIsNone(error_msg)

    @patch("os.path.isdir")
    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_get_secure_boot_state_disabled(
        self, mock_run, mock_which, mock_isdir
    ):
        """Test secure boot state - disabled."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/mokutil"
        mock_run.return_value = (0, "SecureBoot disabled", "")
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.DISABLED)
        self.assertIsNone(error_msg)

    @patch("os.path.isdir")
    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_get_secure_boot_state_unexpected_output(
        self, mock_run, mock_which, mock_isdir
    ):
        """Test secure boot state - unexpected output."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/mokutil"
        mock_run.return_value = (0, "Unexpected output", "")
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.UNEXPECTED_OUTPUT)
        self.assertIn("Unexpected mokutil output", error_msg)

    @patch("os.path.isdir")
    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_get_secure_boot_state_processing_error(
        self, mock_run, mock_which, mock_isdir
    ):
        """Test secure boot state - processing error."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/mokutil"
        mock_run.return_value = (1, "", "mokutil error")
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.PROCESSING_ERROR)
        self.assertIn("mokutil failed", error_msg)


class TestFITImageSecureBootChecker(unittest.TestCase):
    """Test cases for FITImageSecureBootChecker class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock logger and set it as the global logger
        self.mock_logger = Mock(spec=SecureBootLogger)

        # Import the module and set the global logger
        import check_secure_boot_state

        check_secure_boot_state.logger = self.mock_logger

        self.checker = FITImageSecureBootChecker()

    @patch("shutil.which")
    def test_is_supported_true(self, mock_which):
        """Test FIT support detection - supported."""
        mock_which.return_value = "/usr/bin/dumpimage"
        self.assertTrue(FITImageSecureBootChecker.is_supported())

    @patch("shutil.which")
    def test_is_supported_false(self, mock_which):
        """Test FIT support detection - not supported."""
        mock_which.return_value = None
        self.assertFalse(FITImageSecureBootChecker.is_supported())

    def test_get_snap_kernel_patterns(self):
        """Test snap kernel pattern generation."""
        patterns = FITImageSecureBootChecker._get_snap_kernel_patterns()
        expected_patterns = [
            "/snap/*/current/kernel.img",
            "/snap/*/*/kernel.img",
            "/var/lib/snapd/seed/systems/*/kernel/kernel.img",
            "/run/mnt/ubuntu-boot/uboot/ubuntu/*/kernel.img",
            "/boot/uboot/*/kernel.img",
        ]
        self.assertEqual(patterns, expected_patterns)

    def test_get_classic_fit_patterns(self):
        """Test classic FIT pattern generation."""
        patterns = FITImageSecureBootChecker._get_classic_fit_patterns()
        expected_patterns = [
            "/boot/*.itb",
            "/boot/*.dtb",
            "/boot/*.img",
            "/boot/*.fit",
            "/boot/*.dtbo",
            "/boot/dtb/*.dtb",
            "/boot/dtb/*.itb",
            "/boot/dtb/*.fit",
            "/boot/vmlinuz-*",
            "/boot/initrd.img-*",
        ]
        self.assertEqual(patterns, expected_patterns)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="kernel=/boot/vmlinuz-5.4.0",
    )
    @patch("os.path.exists")
    def test_get_boot_kernel_path_from_cmdline(self, mock_exists, mock_file):
        """Test boot kernel path detection from cmdline."""
        mock_exists.return_value = True
        path = FITImageSecureBootChecker._get_boot_kernel_path()
        self.assertEqual(path, "/boot/vmlinuz-5.4.0")

    @patch("builtins.open", side_effect=IOError("test error"))
    @patch("os.path.exists")
    def test_get_boot_kernel_path_cmdline_error(self, mock_exists, mock_file):
        """Test boot kernel path detection when cmdline read fails."""
        mock_exists.return_value = False
        path = FITImageSecureBootChecker._get_boot_kernel_path()
        self.assertIsNone(path)

    @patch("builtins.open", new_callable=mock_open, read_data="root=/dev/sda1")
    @patch("os.path.exists")
    @patch("os.uname")
    def test_get_boot_kernel_path_common_locations(
        self, mock_uname, mock_exists, mock_file
    ):
        """Test boot kernel path detection from common locations."""
        mock_uname.return_value.release = "5.4.0"
        mock_exists.side_effect = [
            False,
            True,
        ]  # First path doesn't exist, second does
        path = FITImageSecureBootChecker._get_boot_kernel_path()
        self.assertEqual(path, "/boot/vmlinuz-5.4.0")

    @patch("builtins.open", new_callable=mock_open, read_data="root=/dev/sda1")
    @patch("os.path.exists")
    @patch("os.uname")
    def test_get_boot_kernel_path_not_found(
        self, mock_uname, mock_exists, mock_file
    ):
        """Test boot kernel path detection when not found."""
        mock_uname.return_value.release = "5.4.0"
        mock_exists.return_value = False
        path = FITImageSecureBootChecker._get_boot_kernel_path()
        self.assertIsNone(path)

    @patch("shutil.which")
    def test_get_secure_boot_state_not_supported(self, mock_which):
        """Test secure boot state when dumpimage not available."""
        mock_which.return_value = None
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.NOT_SUPPORTED)
        self.assertIn("dumpimage command not found", error_msg)

    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker._find_fit_images"
    )
    def test_get_secure_boot_state_no_images(self, mock_find, mock_which):
        """Test secure boot state when no images found."""
        mock_which.return_value = "/usr/bin/dumpimage"
        mock_find.return_value = []
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.NO_IMAGES_FOUND)

    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker._find_fit_images"
    )
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker"
        "._check_fit_image_signature"
    )
    def test_get_secure_boot_state_signed_images(
        self, mock_check, mock_find, mock_which
    ):
        """Test secure boot state with signed images."""
        mock_which.return_value = "/usr/bin/dumpimage"
        mock_find.return_value = ["/boot/test.img"]
        mock_check.return_value = (True, None)
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.ENABLED)
        self.assertIsNone(error_msg)

    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker._find_fit_images"
    )
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker"
        "._check_fit_image_signature"
    )
    def test_get_secure_boot_state_unsigned_images(
        self, mock_check, mock_find, mock_which
    ):
        """Test secure boot state with unsigned images."""
        mock_which.return_value = "/usr/bin/dumpimage"
        mock_find.return_value = ["/boot/test.img"]
        mock_check.return_value = (False, "No signature found")
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.DISABLED)
        self.assertIsNone(error_msg)

    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker._find_fit_images"
    )
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker"
        "._check_fit_image_signature"
    )
    def test_get_secure_boot_state_processing_error(
        self, mock_check, mock_find, mock_which
    ):
        """Test secure boot state with processing error."""
        mock_which.return_value = "/usr/bin/dumpimage"
        mock_find.return_value = ["/boot/test.img"]
        mock_check.return_value = (False, "dumpimage failed")
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.PROCESSING_ERROR)
        self.assertIn("Failed to process kernel images", error_msg)

    @patch("shutil.which")
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker._find_fit_images"
    )
    @patch(
        "check_secure_boot_state.FITImageSecureBootChecker"
        "._check_fit_image_signature"
    )
    def test_get_secure_boot_state_mixed_signatures(
        self, mock_check, mock_find, mock_which
    ):
        """Test secure boot state with mixed signature states."""
        mock_which.return_value = "/usr/bin/dumpimage"
        mock_find.return_value = ["/boot/test1.img", "/boot/test2.img"]
        mock_check.side_effect = [
            (True, None),  # First image signed
            (False, "No signature found"),  # Second image unsigned
        ]
        state, error_msg = self.checker.get_secure_boot_state()
        self.assertEqual(state, SecureBootState.PROCESSING_ERROR)
        self.assertIn("Mixed signature state", error_msg)

    def test_get_no_images_error_core(self):
        """Test no images error for Core variant."""
        self.checker.ubuntu_variant = UbuntuVariant.CORE
        self.checker.hostfs_prefix = ""
        state, error_msg = self.checker._get_no_images_error()
        self.assertEqual(state, SecureBootState.NO_IMAGES_FOUND)
        self.assertIn(
            "No snap kernel images found on Ubuntu Core system", error_msg
        )

    def test_get_no_images_error_classic(self):
        """Test no images error for Classic variant."""
        self.checker.ubuntu_variant = UbuntuVariant.CLASSIC
        self.checker.hostfs_prefix = ""
        state, error_msg = self.checker._get_no_images_error()
        self.assertEqual(state, SecureBootState.NO_IMAGES_FOUND)
        self.assertIn("No FIT images found on the system", error_msg)

    def test_get_no_images_error_with_hostfs(self):
        """Test no images error with hostfs prefix."""
        self.checker.ubuntu_variant = UbuntuVariant.CORE
        self.checker.hostfs_prefix = "/var/lib/snapd/hostfs"
        state, error_msg = self.checker._get_no_images_error()
        self.assertIn("(checked with hostfs access)", error_msg)

    def test_determine_signature_state_all_signed(self):
        """Test signature state determination - all signed."""
        signed = ["/boot/test1.img", "/boot/test2.img"]
        unsigned = []
        state, error_msg = (
            FITImageSecureBootChecker._determine_signature_state(
                signed, unsigned
            )
        )
        self.assertEqual(state, SecureBootState.ENABLED)
        self.assertIsNone(error_msg)

    def test_determine_signature_state_all_unsigned(self):
        """Test signature state determination - all unsigned."""
        signed = []
        unsigned = ["/boot/test1.img", "/boot/test2.img"]
        state, error_msg = (
            FITImageSecureBootChecker._determine_signature_state(
                signed, unsigned
            )
        )
        self.assertEqual(state, SecureBootState.DISABLED)
        self.assertIsNone(error_msg)

    def test_determine_signature_state_mixed(self):
        """Test signature state determination - mixed."""
        signed = ["/boot/test1.img"]
        unsigned = ["/boot/test2.img"]
        state, error_msg = (
            FITImageSecureBootChecker._determine_signature_state(
                signed, unsigned
            )
        )
        self.assertEqual(state, SecureBootState.PROCESSING_ERROR)
        self.assertIn("Mixed signature state", error_msg)

    def test_determine_signature_state_none(self):
        """Test signature state determination - none."""
        signed = []
        unsigned = []
        state, error_msg = (
            FITImageSecureBootChecker._determine_signature_state(
                signed, unsigned
            )
        )
        self.assertEqual(state, SecureBootState.NOT_SUPPORTED)
        self.assertIn(
            "Could not determine FIT image signature status", error_msg
        )

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_check_fit_image_signature_signed(self, mock_run):
        """Test FIT image signature checking - signed."""
        mock_run.return_value = (0, "signature: test", "")
        is_signed, error_msg = self.checker._check_fit_image_signature(
            "/boot/test.img"
        )
        self.assertTrue(is_signed)
        self.assertIsNone(error_msg)

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_check_fit_image_signature_unsigned(self, mock_run):
        """Test FIT image signature checking - unsigned."""
        mock_run.return_value = (0, "completely unrelated output", "")
        is_signed, error_msg = self.checker._check_fit_image_signature(
            "/boot/test.img"
        )
        self.assertFalse(is_signed)
        self.assertIn("No signature found", error_msg)

    @patch(
        "check_secure_boot_state.SecureBootChecker._run_command_with_timeout"
    )
    def test_check_fit_image_signature_error(self, mock_run):
        """Test FIT image signature checking - error."""
        mock_run.return_value = (1, "", "dumpimage error")
        is_signed, error_msg = self.checker._check_fit_image_signature(
            "/boot/test.img"
        )
        self.assertFalse(is_signed)
        self.assertIn("dumpimage failed", error_msg)


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock logger and set it as the global logger
        self.mock_logger = Mock(spec=SecureBootLogger)

        # Import the module and set the global logger
        import check_secure_boot_state

        check_secure_boot_state.logger = self.mock_logger

    def test_log_secure_boot_info(self):
        """Test secure boot info logging."""
        state = SecureBootState.ENABLED
        error_msg = None
        checker_name = "Test Checker"
        log_secure_boot_info(state, error_msg, checker_name)
        self.mock_logger.info.assert_called()

    def test_log_secure_boot_info_with_error(self):
        """Test secure boot info logging with error."""
        state = SecureBootState.PROCESSING_ERROR
        error_msg = "Test error"
        checker_name = "Test Checker"
        log_secure_boot_info(state, error_msg, checker_name)
        self.mock_logger.error.assert_called_with("Error: Test error")

    def test_check_secure_boot_result_processing_error(self):
        """Test secure boot result checking - processing error."""
        state = SecureBootState.PROCESSING_ERROR
        error_msg = "Test error"
        check_mode = "enable"
        result = check_secure_boot_result(state, error_msg, check_mode)
        self.assertEqual(result, 1)
        self.mock_logger.error.assert_called()

    def test_check_secure_boot_result_processing_error_no_mode(self):
        """Test secure boot result checking - processing error without mode."""
        state = SecureBootState.PROCESSING_ERROR
        error_msg = "Test error"
        check_mode = None
        result = check_secure_boot_result(state, error_msg, check_mode)
        self.assertEqual(result, 1)
        self.mock_logger.error.assert_called()

    def test_check_secure_boot_result_enable_success(self):
        """Test secure boot result checking - enable success."""
        state = SecureBootState.ENABLED
        error_msg = None
        check_mode = "enable"
        result = check_secure_boot_result(state, error_msg, check_mode)
        self.assertEqual(result, 0)
        self.mock_logger.info.assert_called()

    def test_check_secure_boot_result_enable_failure(self):
        """Test secure boot result checking - enable failure."""
        state = SecureBootState.DISABLED
        error_msg = None
        check_mode = "enable"
        result = check_secure_boot_result(state, error_msg, check_mode)
        self.assertEqual(result, 1)
        self.mock_logger.log_failure.assert_called()

    def test_check_secure_boot_result_disabled_success(self):
        """Test secure boot result checking - disabled success."""
        state = SecureBootState.DISABLED
        error_msg = None
        check_mode = "disabled"
        result = check_secure_boot_result(state, error_msg, check_mode)
        self.assertEqual(result, 0)
        self.mock_logger.info.assert_called()

    def test_check_secure_boot_result_disabled_failure(self):
        """Test secure boot result checking - disabled failure."""
        state = SecureBootState.ENABLED
        error_msg = None
        check_mode = "disabled"
        result = check_secure_boot_result(state, error_msg, check_mode)
        self.assertEqual(result, 1)
        self.mock_logger.log_failure.assert_called()

    def test_check_secure_boot_result_no_mode(self):
        """Test secure boot result checking - no mode specified."""
        state = SecureBootState.ENABLED
        error_msg = None
        check_mode = None
        result = check_secure_boot_result(state, error_msg, check_mode)
        self.assertEqual(result, 0)

    @patch("check_secure_boot_state.UEFISecureBootChecker.is_supported")
    def test_create_checker_auto_uefi(self, mock_supported):
        """Test checker creation - auto with UEFI support."""
        mock_supported.return_value = True
        checker, name = create_checker(CheckerType.AUTO)
        self.assertIsInstance(checker, UEFISecureBootChecker)
        self.assertIn("UEFI", name)

    @patch("check_secure_boot_state.UEFISecureBootChecker.is_supported")
    @patch("check_secure_boot_state.FITImageSecureBootChecker.is_supported")
    def test_create_checker_auto_fit(
        self, mock_fit_supported, mock_uefi_supported
    ):
        """Test checker creation - auto with FIT support."""
        mock_uefi_supported.return_value = False
        mock_fit_supported.return_value = True
        checker, name = create_checker(CheckerType.AUTO)
        self.assertIsInstance(checker, FITImageSecureBootChecker)
        self.assertIn("FIT", name)

    @patch("check_secure_boot_state.UEFISecureBootChecker.is_supported")
    @patch("check_secure_boot_state.FITImageSecureBootChecker.is_supported")
    def test_create_checker_auto_none_supported(
        self, mock_fit_supported, mock_uefi_supported
    ):
        """Test checker creation - auto with no support."""
        mock_uefi_supported.return_value = False
        mock_fit_supported.return_value = False
        with self.assertRaises(SecureBootNotSupportedError):
            create_checker(CheckerType.AUTO)

    @patch("check_secure_boot_state.UEFISecureBootChecker.is_supported")
    def test_create_checker_uefi_supported(self, mock_supported):
        """Test checker creation - UEFI method supported."""
        mock_supported.return_value = True
        checker, name = create_checker(CheckerType.UEFI)
        self.assertIsInstance(checker, UEFISecureBootChecker)

    @patch("check_secure_boot_state.UEFISecureBootChecker.is_supported")
    def test_create_checker_uefi_not_supported(self, mock_supported):
        """Test checker creation - UEFI method not supported."""
        mock_supported.return_value = False
        with self.assertRaises(SecureBootNotSupportedError):
            create_checker(CheckerType.UEFI)

    @patch("check_secure_boot_state.FITImageSecureBootChecker.is_supported")
    def test_create_checker_fit_supported(self, mock_supported):
        """Test checker creation - FIT method supported."""
        mock_supported.return_value = True
        checker, name = create_checker(CheckerType.FIT)
        self.assertIsInstance(checker, FITImageSecureBootChecker)

    @patch("check_secure_boot_state.FITImageSecureBootChecker.is_supported")
    def test_create_checker_fit_not_supported(self, mock_supported):
        """Test checker creation - FIT method not supported."""
        mock_supported.return_value = False
        with self.assertRaises(SecureBootNotSupportedError):
            create_checker(CheckerType.FIT)

    def test_create_parser(self):
        """Test argument parser creation."""
        parser = create_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

        # Test that all expected arguments are present
        args = parser.parse_args(["--enable", "--verbose", "--method", "uefi"])
        self.assertTrue(args.enable)
        self.assertTrue(args.verbose)
        self.assertEqual(args.method, "uefi")


class TestMainFunction(unittest.TestCase):
    """Test cases for main function."""

    @patch("sys.exit")
    @patch("check_secure_boot_state.create_checker")
    @patch("check_secure_boot_state.create_parser")
    @patch("check_secure_boot_state.SecureBootLogger")
    def test_main_success(
        self,
        mock_logger_class,
        mock_create_parser,
        mock_create_checker,
        mock_exit,
    ):
        """Test main function - success case."""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.enable = True
        mock_args.disabled = False
        mock_args.verbose = True
        mock_args.method = "auto"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        # Mock checker
        mock_checker = Mock()
        mock_checker.get_secure_boot_state.return_value = (
            SecureBootState.ENABLED,
            None,
        )
        mock_create_checker.return_value = (mock_checker, "Test Checker")

        # Mock logger
        mock_logger = Mock()
        mock_logger_class.return_value = mock_logger

        with patch("check_secure_boot_state.logger", mock_logger):
            main()

        mock_exit.assert_called_with(0)

    @patch("sys.exit")
    @patch("check_secure_boot_state.create_checker")
    @patch("check_secure_boot_state.create_parser")
    @patch("check_secure_boot_state.SecureBootLogger")
    def test_main_configuration_error(
        self,
        mock_logger_class,
        mock_create_parser,
        mock_create_checker,
        mock_exit,
    ):
        """Test main function - SecureBootConfigurationError."""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.enable = False
        mock_args.disabled = False
        mock_args.verbose = False
        mock_args.method = "auto"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        # Mock checker creation to raise SecureBootConfigurationError
        mock_create_checker.side_effect = SecureBootConfigurationError(
            "Invalid method"
        )

        # Mock logger
        mock_logger = Mock()
        mock_logger_class.return_value = mock_logger

        with patch("check_secure_boot_state.logger", mock_logger):
            main()

        mock_exit.assert_called_with(1)

    @patch("sys.exit")
    @patch("check_secure_boot_state.create_checker")
    @patch("check_secure_boot_state.create_parser")
    @patch("check_secure_boot_state.SecureBootLogger")
    def test_main_not_supported_error(
        self,
        mock_logger_class,
        mock_create_parser,
        mock_create_checker,
        mock_exit,
    ):
        """Test main function - SecureBootNotSupportedError."""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.enable = False
        mock_args.disabled = False
        mock_args.verbose = False
        mock_args.method = "auto"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        # Mock checker creation to raise SecureBootNotSupportedError
        mock_create_checker.side_effect = SecureBootNotSupportedError(
            "No supported method"
        )

        # Mock logger
        mock_logger = Mock()
        mock_logger_class.return_value = mock_logger

        with patch("check_secure_boot_state.logger", mock_logger):
            main()

        mock_exit.assert_called_with(1)

    @patch("sys.exit")
    @patch("check_secure_boot_state.create_checker")
    @patch("check_secure_boot_state.create_parser")
    @patch("check_secure_boot_state.SecureBootLogger")
    def test_main_keyboard_interrupt(
        self,
        mock_logger_class,
        mock_create_parser,
        mock_create_checker,
        mock_exit,
    ):
        """Test main function - KeyboardInterrupt."""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.enable = False
        mock_args.disabled = False
        mock_args.verbose = False
        mock_args.method = "auto"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        # Mock checker creation to raise KeyboardInterrupt
        mock_create_checker.side_effect = KeyboardInterrupt()

        # Mock logger
        mock_logger = Mock()
        mock_logger_class.return_value = mock_logger

        with patch("check_secure_boot_state.logger", mock_logger):
            main()

        mock_exit.assert_called_with(1)

    @patch("sys.exit")
    @patch("check_secure_boot_state.create_checker")
    @patch("check_secure_boot_state.create_parser")
    @patch("check_secure_boot_state.SecureBootLogger")
    def test_main_unexpected_error(
        self,
        mock_logger_class,
        mock_create_parser,
        mock_create_checker,
        mock_exit,
    ):
        """Test main function - unexpected error."""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.enable = False
        mock_args.disabled = False
        mock_args.verbose = True  # Enable verbose for traceback
        mock_args.method = "auto"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        # Mock checker creation to raise unexpected error
        mock_create_checker.side_effect = Exception("Unexpected error")

        # Mock logger
        mock_logger = Mock()
        mock_logger_class.return_value = mock_logger

        with patch("check_secure_boot_state.logger", mock_logger):
            with patch("traceback.print_exc") as mock_traceback:
                main()

        mock_exit.assert_called_with(1)
        mock_traceback.assert_called_once()

    @patch("sys.exit")
    @patch("check_secure_boot_state.create_checker")
    @patch("check_secure_boot_state.create_parser")
    @patch("check_secure_boot_state.SecureBootLogger")
    def test_main_unexpected_error_no_verbose(
        self,
        mock_logger_class,
        mock_create_parser,
        mock_create_checker,
        mock_exit,
    ):
        """Test main function - unexpected error without verbose."""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.enable = False
        mock_args.disabled = False
        mock_args.verbose = False  # Disable verbose
        mock_args.method = "auto"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        # Mock checker creation to raise unexpected error
        mock_create_checker.side_effect = Exception("Unexpected error")

        # Mock logger
        mock_logger = Mock()
        mock_logger_class.return_value = mock_logger

        with patch("check_secure_boot_state.logger", mock_logger):
            with patch("traceback.print_exc") as mock_traceback:
                main()

        mock_exit.assert_called_with(1)
        mock_traceback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
