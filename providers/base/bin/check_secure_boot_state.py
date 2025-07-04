#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Isaac Yang    <isaac.yang@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.
"""
Check Secure Boot State

This script provides comprehensive secure boot state checking for Ubuntu
systems. It supports both UEFI-based secure boot (using mokutil) and FIT
image-based secure boot (using dumpimage) for Ubuntu Classic and Ubuntu
Core systems.

The script can validate secure boot states against expected values and provides
detailed logging for troubleshooting. It automatically detects the appropriate
checking method based on system capabilities.

Supported Systems:
- Ubuntu Classic (x86_64, aarch64, armhf)
- Ubuntu Core (x86_64, aarch64, armhf)
- UEFI-based secure boot systems
- FIT image-based secure boot systems

Usage Examples:
    check_secure_boot_state.py --enable    # Check if secure boot is enabled
    check_secure_boot_state.py --disabled  # Check if secure boot is disabled
    check_secure_boot_state.py --verbose   # Show detailed secure boot state
    check_secure_boot_state.py --method uefi --enable  # Force UEFI method
    check_secure_boot_state.py --method fit --verbose  # Force FIT method

Exit Codes:
    0 - Success (secure boot state matches expectation or no validation
       requested)
    1 - Failure (secure boot state doesn't match expectation or error
       occurred)
"""

import argparse
import subprocess
import sys
import os
import shutil
import logging
import glob
from abc import ABC, abstractmethod
from typing import Tuple, List, Optional
from enum import Enum

# Global logger instance
logger: "SecureBootLogger" = None


class SecureBootLogger:
    """Centralized logging for secure boot state checking."""

    def __init__(self, verbose: bool = False):
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(message)s",
            handlers=[logging.StreamHandler()],
        )
        self.verbose = verbose

    def debug(self, message: str, *args) -> None:
        """Log debug message with optional formatting."""
        if args:
            logging.debug(message.format(*args))
        else:
            logging.debug(message)

    def info(self, message: str, *args) -> None:
        """Log info message with optional formatting."""
        if args:
            logging.info(message.format(*args))
        else:
            logging.info(message)

    def warning(self, message: str, *args) -> None:
        """Log warning message with optional formatting."""
        if args:
            logging.warning(message.format(*args))
        else:
            logging.warning(message)

    def error(self, message: str, *args) -> None:
        """Log error message with optional formatting."""
        if args:
            logging.error(message.format(*args))
        else:
            logging.error(message)

    def log_failure(
        self, expected_state: str, actual_state: str, error_msg: Optional[str]
    ) -> None:
        """Log failure message for secure boot state checks."""
        if error_msg:
            self.error(
                "FAIL: Secure boot is not {} - {}", expected_state, error_msg
            )
        else:
            self.error(
                "FAIL: Secure boot is not {} (current state: {})",
                expected_state,
                actual_state,
            )


class SecureBootState(Enum):
    """Enumeration of possible secure boot states."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    NOT_SUPPORTED = "not_supported"
    NO_IMAGES_FOUND = "no_images_found"
    PROCESSING_ERROR = "processing_error"
    UNEXPECTED_OUTPUT = "unexpected_output"


class SecureBootError(Exception):
    """Base exception for secure boot related errors."""

    pass


class SecureBootProcessingError(SecureBootError):
    """Exception raised when secure boot processing fails."""

    pass


class SecureBootNotSupportedError(SecureBootError):
    """Exception raised when secure boot is not supported on the system."""

    pass


class SecureBootConfigurationError(SecureBootError):
    """Exception raised when there's a configuration error."""

    pass


class UbuntuVariant(Enum):
    """Enumeration of Ubuntu variants."""

    CORE = "core"
    CLASSIC = "classic"
    UNKNOWN = "unknown"


class CheckerType(Enum):
    """Enumeration of secure boot checker types."""

    UEFI = "uefi"
    FIT = "fit"
    AUTO = "auto"


class SecureBootChecker(ABC):
    """
    Abstract base class for secure boot checking methods.

    This class provides common functionality for different secure boot checking
    implementations, including hostfs prefix handling for snap environments,
    Ubuntu variant detection, and utility methods for file operations and
    command execution.
    """

    def __init__(self):
        """Initialize the checker with common utilities."""
        self.hostfs_prefix = self._get_hostfs_prefix()
        self.ubuntu_variant = self._detect_ubuntu_variant()
        logger.debug(
            "Initialized {} with hostfs_prefix='{}', ubuntu_variant='{}'",
            self.__class__.__name__,
            self.hostfs_prefix,
            self.ubuntu_variant,
        )

    @staticmethod
    def _get_hostfs_prefix() -> str:
        """
        Get the hostfs prefix for accessing host files when running in a
        snap.
        ref: https://snapcraft.io/docs/the-system-backup-interface
        """
        return "/var/lib/snapd/hostfs" if os.environ.get("SNAP") else ""

    def _detect_ubuntu_variant(self) -> UbuntuVariant:
        """
        Detect the Ubuntu variant using hostnamectl.

        Returns:
            UbuntuVariant enum value (CORE, CLASSIC, or UNKNOWN)
        """
        try:
            return_code, stdout, stderr = self._run_command_with_timeout(
                ["hostnamectl"], timeout=5
            )
            if return_code == 0 and stdout:
                if "Ubuntu Core" in stdout:
                    logger.debug("Detected Ubuntu Core via hostnamectl")
                    return UbuntuVariant.CORE
                elif "Ubuntu" in stdout:
                    logger.debug("Detected Ubuntu Classic via hostnamectl")
                    return UbuntuVariant.CLASSIC
                else:
                    logger.debug("Unknown OS via hostnamectl: {}", stdout[:50])
                    return UbuntuVariant.UNKNOWN
            else:
                logger.debug("hostnamectl failed or returned no output")
                return UbuntuVariant.UNKNOWN
        except Exception as e:
            logger.debug("Failed to run hostnamectl: {}", e)
            return UbuntuVariant.UNKNOWN

    def _build_search_patterns(self, base_patterns: List[str]) -> List[str]:
        """
        Build search patterns with hostfs prefix prioritized if in snap
        environment.
        """
        if self.hostfs_prefix:
            # Prioritize hostfs patterns when running in snap environment
            hostfs_patterns = [
                self.hostfs_prefix + pattern for pattern in base_patterns
            ]
            return hostfs_patterns + base_patterns
        return list(base_patterns)

    def _find_files_by_patterns(self, patterns: List[str]) -> List[str]:
        """
        Find files matching the given patterns.

        Args:
            patterns: List of glob patterns to search

        Returns:
            List of matching file paths (deduplicated)
        """
        found_files = []
        for pattern in patterns:
            try:
                matches = glob.glob(pattern)
                found_files.extend(matches)
            except Exception as e:
                logger.debug(
                    "Failed to search pattern '{}': {}".format(pattern, e)
                )
                continue

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for file_path in found_files:
            if file_path not in seen:
                seen.add(file_path)
                unique_files.append(file_path)

        return unique_files

    @staticmethod
    def _run_command_with_timeout(
        cmd: List[str], timeout: int = 10
    ) -> Tuple[int, str, str]:
        """
        Run a command with timeout and return results.

        Args:
            cmd: Command to run as a list of strings
            timeout: Timeout in seconds

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                return (
                    -1,
                    "",
                    "Command timed out after {} seconds".format(timeout),
                )
            return proc.returncode, stdout.strip(), stderr.strip()
        except OSError as e:
            return (
                -1,
                "",
                "Command not found or not executable: {}".format(str(e)),
            )
        except Exception as e:
            return -1, "", "Subprocess error: {}".format(str(e))

    @abstractmethod
    def get_secure_boot_state(self) -> Tuple[SecureBootState, Optional[str]]:
        """
        Get the current secure boot state.

        Returns:
            Tuple containing (state, error_message) where state is a
            SecureBootState enum value and error_message is None for
            success states or a descriptive error message for error states
        """
        pass

    @abstractmethod
    def is_supported(self) -> bool:
        """
        Check if this secure boot method is supported on the system.

        Returns:
            True if supported, False otherwise
        """
        pass


class UEFISecureBootChecker(SecureBootChecker):
    """
    UEFI-based secure boot checker using mokutil.

    This checker uses the mokutil command to query the UEFI secure boot state.
    It's the preferred method for UEFI-based systems as it provides direct
    access to the firmware's secure boot configuration.
    """

    @classmethod
    def is_supported(cls) -> bool:
        """
        Check if UEFI secure boot is supported.

        Returns:
            True if UEFI is supported, False otherwise
        """
        return os.path.isdir("/sys/firmware/efi")

    def get_secure_boot_state(self) -> Tuple[SecureBootState, Optional[str]]:
        """
        Get the current UEFI secure boot state using mokutil.

        Returns:
            Tuple containing (state, error_message) where state is a
            SecureBootState enum value and error_message is None for
            success states or a descriptive error message for error states
        """
        if not self.is_supported():
            return (
                SecureBootState.NOT_SUPPORTED,
                "UEFI is not supported on this system "
                "(no /sys/firmware/efi directory)",
            )

        if not shutil.which("mokutil"):
            return (
                SecureBootState.NOT_SUPPORTED,
                "mokutil command not found - UEFI secure boot checking "
                "not available",
            )

        logger.debug("Running mokutil --sb-state")
        return_code, stdout, stderr = self._run_command_with_timeout(
            ["mokutil", "--sb-state"]
        )

        if return_code == 0:
            if "SecureBoot enabled" in stdout:
                logger.debug("mokutil reports secure boot enabled")
                return (SecureBootState.ENABLED, None)
            elif "SecureBoot disabled" in stdout:
                logger.debug("mokutil reports secure boot disabled")
                return (SecureBootState.DISABLED, None)
            else:
                logger.warning(
                    "Unexpected mokutil output: '{}'".format(stdout)
                )
                return (
                    SecureBootState.UNEXPECTED_OUTPUT,
                    "Unexpected mokutil output: '{}'".format(stdout),
                )
        else:
            # mokutil failed - this is a processing error
            error_msg = stderr.strip() if stderr else "Unknown error"
            logger.error(
                "mokutil failed with return code {}: {}".format(
                    return_code, error_msg
                )
            )
            return (
                SecureBootState.PROCESSING_ERROR,
                "mokutil failed (return code {}): {}".format(
                    return_code, error_msg
                ),
            )


class FITImageSecureBootChecker(SecureBootChecker):
    """
    FIT image-based secure boot checker using dumpimage.

    This checker analyzes FIT (Flattened Image Tree) images to determine
    if they are signed, which indicates secure boot is enabled. It's used
    for systems that don't support UEFI or as a fallback method.
    """

    @classmethod
    def is_supported(cls) -> bool:
        """
        Check if FIT image secure boot is supported.

        Returns:
            True if dumpimage is available, False otherwise
        """
        return shutil.which("dumpimage") is not None

    @staticmethod
    def _get_snap_kernel_patterns() -> List[str]:
        """
        Get patterns for snap kernel images.

        These patterns are used to find kernel images in Ubuntu Core
        snap environments.

        Returns:
            List of glob patterns for snap kernel images
        """
        return [
            "/snap/*/current/kernel.img",
            "/snap/*/*/kernel.img",
            "/var/lib/snapd/seed/systems/*/kernel/kernel.img",
            "/run/mnt/ubuntu-boot/uboot/ubuntu/*/kernel.img",
            "/boot/uboot/*/kernel.img",
        ]

    @staticmethod
    def _get_boot_kernel_path() -> Optional[str]:
        """
        Get the path to the currently booted kernel image.

        This method attempts to determine the path of the currently
        booted kernel by examining /proc/cmdline and common kernel
        locations.

        Returns:
            Path to the boot kernel image or None if not found
        """
        # Try to get the boot kernel path from /proc/cmdline
        try:
            with open("/proc/cmdline", "r") as f:
                cmdline = f.read().strip()

            # Look for kernel= parameter in cmdline
            for param in cmdline.split():
                if param.startswith("kernel="):
                    kernel_path = param.split("=", 1)[1]
                    if os.path.exists(kernel_path):
                        logger.debug(
                            "Found boot kernel from cmdline: {}".format(
                                kernel_path
                            )
                        )
                        return kernel_path
        except (IOError, OSError) as e:
            logger.debug("Failed to read /proc/cmdline: {}".format(e))

        # Fallback: try common boot kernel locations
        common_paths = [
            "/boot/vmlinuz",
            "/boot/vmlinuz-{}".format(os.uname().release),
            "/boot/kernel.img",
            "/boot/Image",
        ]

        for path in common_paths:
            if os.path.exists(path):
                logger.debug(
                    "Found boot kernel at common location: {}".format(path)
                )
                return path

        logger.debug(
            "No boot kernel found in common locations: {}".format(common_paths)
        )
        return None

    @staticmethod
    def _get_classic_fit_patterns() -> List[str]:
        """
        Get patterns for classic FIT images.

        These patterns are used to find kernel and FIT images in
        Ubuntu Classic environments.

        Returns:
            List of glob patterns for classic FIT images
        """
        return [
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

    def _find_fit_images(self) -> List[str]:
        """
        Find the boot kernel image for secure boot validation.

        This method attempts to locate the currently booted kernel image
        or suitable FIT images for signature verification. It prioritizes
        the actual boot kernel over other kernel images.

        Returns:
            List containing the boot kernel image path (or empty list if
            not found)
        """
        logger.debug("Detected Ubuntu variant: {}".format(self.ubuntu_variant))
        if self.hostfs_prefix:
            logger.debug(
                "Running in snap environment, using hostfs prefix: {}".format(
                    self.hostfs_prefix
                )
            )

        # Try to get the boot kernel path first
        boot_kernel = self._get_boot_kernel_path()
        if boot_kernel:
            logger.debug("Found boot kernel: {}".format(boot_kernel))
            return [boot_kernel]

        if self.ubuntu_variant == UbuntuVariant.CORE:
            pattern_func = self._get_snap_kernel_patterns
            not_found_msg = "No snap kernel images found"
            found_msg = "Using snap kernel: {}"
        else:
            pattern_func = self._get_classic_fit_patterns
            not_found_msg = "No classic kernel images found"
            found_msg = "Using first classic kernel found: {}"

        patterns = self._build_search_patterns(pattern_func())
        logger.debug(
            "Search patterns (hostfs prioritized): {}".format(patterns)
        )
        images = self._find_files_by_patterns(patterns)
        if images:
            boot_kernel = images[0]
            logger.debug(found_msg.format(boot_kernel))
            return [boot_kernel]
        logger.debug(not_found_msg)
        return []

    def _check_fit_image_signature(
        self, image_path: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a FIT image is signed using dumpimage.

        Args:
            image_path: Path to the FIT image

        Returns:
            Tuple containing (is_signed, error_message)
        """
        logger.debug("Checking signature of image: {}".format(image_path))
        return_code, stdout, stderr = self._run_command_with_timeout(
            ["dumpimage", "-l", image_path]
        )

        if return_code == 0:
            # Check for signature information in dumpimage output
            if "signature" in stdout.lower() or "sign" in stdout.lower():
                logger.debug("Image {} is signed".format(image_path))
                return (True, None)
            else:
                logger.debug("Image {} is not signed".format(image_path))
                return (False, "No signature found in FIT image")
        else:
            # dumpimage failed - this could be due to various reasons:
            # 1. Image is not a valid FIT format
            # 2. Image is corrupted
            # 3. dumpimage cannot process this type of image
            # 4. Permission issues
            error_msg = stderr.strip() if stderr else "Unknown error"
            logger.debug(
                "dumpimage failed for {} (return code {}): {}".format(
                    image_path, return_code, error_msg
                )
            )
            return (
                False,
                "dumpimage failed (return code {}): {}".format(
                    return_code, error_msg
                ),
            )

    def get_secure_boot_state(self) -> Tuple[SecureBootState, Optional[str]]:
        """
        Get the current FIT image secure boot state.

        This method analyzes FIT images to determine if they are signed,
        which indicates secure boot is enabled. It handles various error
        conditions and provides detailed error messages.

        Returns:
            Tuple containing (state, error_message) where state is a
            SecureBootState enum value and error_message is None for
            success states or a descriptive error message for error states
        """
        if not self.is_supported():
            return (
                SecureBootState.NOT_SUPPORTED,
                "dumpimage command not found - FIT image secure boot "
                "checking not available",
            )

        # Find FIT images
        fit_images = self._find_fit_images()

        if not fit_images:
            return self._get_no_images_error()

        # Check each image for signatures
        signed_images = []
        unsigned_images = []
        processing_errors = []

        for image_path in fit_images:
            logger.debug("Checking image: {}".format(image_path))
            is_signed, error_msg = self._check_fit_image_signature(image_path)

            if is_signed:
                signed_images.append(image_path)
                logger.debug("Image {} is signed".format(image_path))
            elif error_msg and "dumpimage failed" in error_msg:
                # This is a processing error, not an unsigned image
                processing_errors.append((image_path, error_msg))
                logger.debug(
                    "Image {} processing error: {}".format(
                        image_path, error_msg
                    )
                )
            else:
                # This is truly an unsigned image
                unsigned_images.append(image_path)
                logger.debug(
                    "Image {} is not signed: {}".format(image_path, error_msg)
                )

        # Handle processing errors first
        if processing_errors:
            error_details = "; ".join(
                "{}: {}".format(path, error)
                for path, error in processing_errors
            )
            return (
                SecureBootState.PROCESSING_ERROR,
                "Failed to process kernel images: {}".format(error_details),
            )

        # Determine overall state based on signed/unsigned images
        return self._determine_signature_state(signed_images, unsigned_images)

    def _get_no_images_error(self) -> Tuple[SecureBootState, str]:
        """
        Get appropriate error message for no images found.

        Returns:
            Tuple containing (state, error_message) with context-specific
            error message based on Ubuntu variant and environment
        """
        if self.ubuntu_variant == UbuntuVariant.CORE:
            base_msg = "No snap kernel images found on Ubuntu Core system"
        else:
            base_msg = "No FIT images found on the system"

        # Add hostfs context if applicable
        if self.hostfs_prefix:
            error_msg = "{} (checked with hostfs access)".format(base_msg)
        else:
            error_msg = base_msg

        return (SecureBootState.NO_IMAGES_FOUND, error_msg)

    @staticmethod
    def _determine_signature_state(
        signed_images: List[str], unsigned_images: List[str]
    ) -> Tuple[SecureBootState, Optional[str]]:
        """
        Determine the overall signature state based on image lists.

        Args:
            signed_images: List of paths to signed images
            unsigned_images: List of paths to unsigned images

        Returns:
            Tuple containing (state, error_message) representing the overall
            signature state
        """
        if signed_images and not unsigned_images:
            return (SecureBootState.ENABLED, None)
        elif unsigned_images and not signed_images:
            return (SecureBootState.DISABLED, None)
        elif signed_images and unsigned_images:
            return (
                SecureBootState.PROCESSING_ERROR,
                "Mixed signature state: {} signed, {} unsigned images".format(
                    len(signed_images), len(unsigned_images)
                ),
            )
        else:
            return (
                SecureBootState.NOT_SUPPORTED,
                "Could not determine FIT image signature status",
            )


def log_secure_boot_info(
    state: SecureBootState, error_msg: Optional[str], checker_name: str
) -> None:
    """
    Log detailed secure boot information.

    Args:
        state: The secure boot state enum value
        error_msg: Error message if any, None otherwise
        checker_name: Name of the checker being used
    """
    logger.info("=== Secure Boot State Check ===")
    logger.info("Checker: {}".format(checker_name))
    logger.info("Current state: {}".format(state.value))
    if error_msg:
        logger.error("Error: {}".format(error_msg))


def check_secure_boot_result(
    state: SecureBootState, error_msg: Optional[str], check_mode: Optional[str]
) -> int:
    """
    Check secure boot result based on the specified mode.

    Args:
        state: The secure boot state
        error_msg: Error message if any, None otherwise
        check_mode: The check mode ('enable', 'disabled', or None)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Early return for processing errors in any mode
    if state == SecureBootState.PROCESSING_ERROR:
        if check_mode:
            logger.error(
                "FAIL: Cannot determine if secure boot is {} - {}".format(
                    check_mode, error_msg
                )
            )
        else:
            logger.error(
                "FAIL: Cannot determine secure boot state - {}".format(
                    error_msg
                )
            )
        return 1

    expected_states = {
        "enable": (SecureBootState.ENABLED, "Secure boot is enabled"),
        "disabled": (SecureBootState.DISABLED, "Secure boot is disabled"),
    }

    if check_mode in expected_states:
        expected_state, success_msg = expected_states[check_mode]
        if state == expected_state:
            logger.info("PASS: {}".format(success_msg))
            return 0
        else:
            logger.log_failure(check_mode, state, error_msg)
            return 1

    # Default mode: just show the state (already logged above)
    return 0


def create_checker(method: CheckerType) -> Tuple[SecureBootChecker, str]:
    """
    Create the appropriate checker based on method.

    Args:
        method: The checking method (UEFI, FIT, or AUTO)

    Returns:
        Tuple of (checker_instance, checker_name)

    Raises:
        SecureBootConfigurationError: If method is not one of the valid
            options
        SecureBootNotSupportedError: If no supported secure boot method is
            found
    """
    # Define available checkers with their support checks and names
    checkers = [
        (UEFISecureBootChecker, "UEFI (mokutil)"),
        (FITImageSecureBootChecker, "FIT Image (dumpimage)"),
    ]

    if method == CheckerType.AUTO:
        # Try each checker in order until one is supported
        for checker_class, checker_name in checkers:
            if checker_class.is_supported():
                checker = checker_class()
                return checker, checker_name

        # No supported method found
        raise SecureBootNotSupportedError(
            "No supported secure boot method found. "
            "Neither UEFI (mokutil) nor FIT (dumpimage) are available."
        )
    else:
        # Find the requested checker
        for checker_class, checker_name in checkers:
            if checker_name.lower().startswith(method.value):
                if not checker_class.is_supported():
                    error_messages = {
                        CheckerType.UEFI: (
                            "UEFI method requested but not supported on this "
                            "system (no /sys/firmware/efi directory)"
                        ),
                        CheckerType.FIT: (
                            "FIT method requested but not supported on this "
                            "system (dumpimage command not found)"
                        ),
                    }
                    raise SecureBootNotSupportedError(error_messages[method])
                checker = checker_class()
                return checker, checker_name

        # This should never happen due to argument validation
        raise SecureBootConfigurationError(
            "Unknown method: {}".format(method.value)
        )


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Check and validate secure boot state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--enable", action="store_true", help="Check if secure boot is enabled"
    )

    parser.add_argument(
        "--disabled",
        action="store_true",
        help="Check if secure boot is disabled",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with debug information",
    )

    parser.add_argument(
        "--method",
        choices=[checker.value for checker in CheckerType],
        default=CheckerType.AUTO.value,
        help=(
            "Secure boot checking method. "
            "'uefi' uses mokutil for UEFI systems, "
            "'fit' uses dumpimage for FIT image analysis, "
            "'auto' automatically selects the best available method "
            "(default: %(default)s)"
        ),
    )

    return parser


def main() -> None:
    """Main entry point for the secure boot state checker."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    global logger
    logger = SecureBootLogger(args.verbose)

    try:
        # Create checker
        method = CheckerType(args.method)
        checker, checker_name = create_checker(method)

        # Get secure boot state
        state, error_msg = checker.get_secure_boot_state()

        # Always log the detailed information
        log_secure_boot_info(state, error_msg, checker_name)

        # Determine check mode and handle result
        check_mode = None
        if args.enable:
            check_mode = "enable"
        elif args.disabled:
            check_mode = "disabled"

        exit_code = check_secure_boot_result(state, error_msg, check_mode)
        sys.exit(exit_code)

    except SecureBootConfigurationError as e:
        logger.error("Configuration error: {}".format(str(e)))
        sys.exit(1)
    except SecureBootNotSupportedError as e:
        logger.error("Not supported error: {}".format(str(e)))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: {}".format(str(e)))
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
