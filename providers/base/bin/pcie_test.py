#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
A Python script to verify PCIe device link capabilities against their current
link status using the 'lspci' command on Linux.
This script is designed for Ubuntu on x86 and ARM64 platforms.
"""

import argparse
import logging
import re
import subprocess
import sys


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.

    Returns:
        logging.Logger: The configured root logger.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(levelname)-8s %(message)s"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


def _run_command(command):
    """
    Executes a shell command and returns its stdout.
    Handles errors and provides clean output.

    Args:
        command (list): The command and its arguments as a list.

    Returns:
        str: The standard output of the command.

    Raises:
        RuntimeError: If the command fails to execute.
    """
    logger = logging.getLogger(__name__)
    try:
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return process.stdout
    except FileNotFoundError:
        error_message = (
            "Error: '{}' command not found. "
            "Please ensure 'pciutils' is installed "
            "(`sudo apt install pciutils`).".format(command[0])
        )
        logger.error(error_message)
        raise RuntimeError(error_message)
    except subprocess.CalledProcessError as e:
        error_message = (
            "Error executing command: '{}'\n"
            "Return Code: {}\n"
            "Stderr: {}".format(
                " ".join(command), e.returncode, e.stderr.strip()
            )
        )
        logger.error(error_message)
        raise RuntimeError(error_message)


class PCIeTester(object):
    """
    A class to handle PCIe device enumeration and link state checking.
    """

    def __init__(self):
        """
        Initializes the PCIeTester with a logger instance.
        """
        self._logger = logging.getLogger(__name__)

    def _parse_link_info(self, line):
        """
        Parses a 'LnkCap' or 'LnkSta' line to extract speed and width.

        Args:
            line (str): A single line of output from 'lspci -vv'.

        Returns:
            tuple: A tuple (speed, width) or (None, None) if not found.
        """
        link_info_pattern = re.compile(
            r"Speed\s+(?P<speed>[\d\.]+GT/s).*Width\s+(?P<width>x\d+)"
        )
        match = link_info_pattern.search(line)
        if match:
            return match.group("speed"), match.group("width")
        return None, None

    def _get_pcie_info(self, pcie_slot):
        """
        Get PCIe device info using lspci.

        Args:
            pcie_slot (str): The BDF identifier.

        Returns:
            str: lspci output, or None if command fails.
        """
        command = ["lspci", "-s", pcie_slot, "-vv"]
        try:
            return _run_command(command)
        except RuntimeError:
            return None

    def list_resources(self):
        """
        Lists all PCIe devices found by 'lspci'.

        Returns:
            int: 0 for success, 1 for failure.
        """
        print("Discovering PCIe resources...")
        try:
            output = _run_command(["lspci"])
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1

        if not output:
            print("No PCIe devices found.")
            return 0

        for line in output.strip().split("\n"):
            parts = line.split(" ", 1)
            pcie_num = parts[0]
            pcie_name = parts[1].strip()
            print("pcie_num: {}".format(pcie_num))
            print("pcie_name: {}".format(pcie_name))
            print("")  # For spacing
        return 0

    def check_link_state(self, pcie_slot, force=False):
        """
        Checks if a PCIe device's link state matches its capability.

        Args:
            pcie_slot (str): The BDF (Bus:Device.Function) identifier
                           (e.g., '00:00.0').
            force (bool): If True, fail when LnkCap/LnkSta not found.

        Returns:
            int: 0 for success (match), 1 for failure (mismatch or error).
        """
        output = self._get_pcie_info(pcie_slot)
        if output is None:
            return 1

        cap_info = {"speed": None, "width": None}
        sta_info = {"speed": None, "width": None}
        lnk_cap_line = None
        lnk_sta_line = None

        for line in output.strip().split("\n"):
            line = line.strip()
            if line.startswith("LnkCap:"):
                lnk_cap_line = line
                speed, width = self._parse_link_info(line)
                cap_info["speed"], cap_info["width"] = speed, width
            elif line.startswith("LnkSta:"):
                lnk_sta_line = line
                speed, width = self._parse_link_info(line)
                sta_info["speed"], sta_info["width"] = speed, width

        cap_found = all(cap_info.values())
        sta_found = all(sta_info.values())

        # If neither LnkCap nor LnkSta is found, device may not report
        # these values. With --force, this is a failure.
        if not cap_found and not sta_found:
            if force:
                self._logger.error(
                    "LnkCap/LnkSta not found for device {} "
                    "(--force enabled).".format(pcie_slot)
                )
                return 1
            else:
                self._logger.info(
                    "LnkCap/LnkSta not found for device {}. "
                    "Skipping link check.".format(pcie_slot)
                )
                return 0

        # If one is found but not the other, it's an unexpected state.
        if not cap_found:
            self._logger.error(
                "Found LnkSta but not LnkCap for device {}.".format(pcie_slot)
            )
            return 1

        if not sta_found:
            self._logger.error(
                "Found LnkCap but not LnkSta for device {}.".format(pcie_slot)
            )
            return 1

        # Both found, proceed with comparison.
        # Log raw data for debugging
        if lnk_cap_line:
            self._logger.debug(lnk_cap_line)
        if lnk_sta_line:
            self._logger.debug(lnk_sta_line)

        self._logger.info(
            "Expect: Speed {}, Width {}".format(
                cap_info["speed"], cap_info["width"]
            )
        )
        self._logger.info(
            "Actually: Speed {}, Width {}".format(
                sta_info["speed"], sta_info["width"]
            )
        )

        if (
            cap_info["speed"] == sta_info["speed"]
            and cap_info["width"] == sta_info["width"]
        ):
            self._logger.info("Those two are match")
            return 0
        else:
            self._logger.error("Those two are not match.")
            return 1

    def check_aspm_state(self, pcie_slot, force=False):
        """
        Checks a device's ASPM capability against its control state.

        Args:
            pcie_slot (str): The BDF (Bus:Device.Function) identifier
                           (e.g., '00:00.0').
            force (bool): If True, fail when ASPM is not supported.

        Returns:
            int: 0 for success (pass), 1 for failure.
        """
        output = self._get_pcie_info(pcie_slot)
        if output is None:
            return 1

        lnk_cap_line = None
        lnk_ctl_line = None

        for line in output.strip().split("\n"):
            line = line.strip()
            if line.startswith("LnkCap:"):
                lnk_cap_line = line
            elif line.startswith("LnkCtl:"):
                lnk_ctl_line = line

        # Log raw data for debugging
        if lnk_cap_line:
            self._logger.debug(lnk_cap_line)
        if lnk_ctl_line:
            self._logger.debug(lnk_ctl_line)

        if not lnk_cap_line:
            if force:
                self._logger.error(
                    "LnkCap not found for device {}. "
                    "Cannot check ASPM (--force enabled).".format(pcie_slot)
                )
                return 1
            else:
                self._logger.info(
                    "LnkCap not found for device {}. "
                    "Cannot check ASPM. Skipping.".format(pcie_slot)
                )
                return 0  # Not an error, just can't test

        # Check for ASPM support in LnkCap
        if "ASPM" not in lnk_cap_line:
            if force:
                self._logger.error(
                    "ASPM not supported by hardware for device {} "
                    "(not listed in LnkCap, --force enabled).".format(
                        pcie_slot
                    )
                )
                self._logger.error("LnkCap: {}".format(lnk_cap_line))
                return 1
            else:
                self._logger.info(
                    "ASPM not supported by hardware for device {} "
                    "(not listed in LnkCap).".format(pcie_slot)
                )
                return 0  # Expected behavior, so it's a pass.

        self._logger.info(
            "ASPM is supported by hardware for device {}.".format(pcie_slot)
        )

        # If ASPM is supported, LnkCtl must exist to check its state.
        if not lnk_ctl_line:
            self._logger.error(
                "LnkCtl not found for device {}, but ASPM is "
                "supported. Cannot verify status.".format(pcie_slot)
            )
            return 1

        # Check if ASPM is disabled in LnkCtl
        if "ASPM Disabled" in lnk_ctl_line:
            self._logger.info("LnkCtl: {}".format(lnk_ctl_line))
            self._logger.error(
                "Fail: ASPM is supported by hardware but is "
                "disabled in LnkCtl."
            )
            return 1
        else:
            self._logger.info("LnkCtl: {}".format(lnk_ctl_line))
            self._logger.info(
                "Pass: ASPM is supported and enabled "
                "(or not explicitly disabled)."
            )
            return 0


def main():
    """
    Main function to parse arguments and run the requested action.
    """
    parser = argparse.ArgumentParser(
        description=(
            "A script to test PCIe link state against " "hardware capability."
        )
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )
    subparsers.required = True

    # 'resource' command
    parser_resource = subparsers.add_parser(
        "resource", help="List all PCIe devices."
    )
    parser_resource.set_defaults(
        func=lambda args, tester: tester.list_resources()
    )

    # 'check_speed' command
    parser_check_speed = subparsers.add_parser(
        "check_speed",
        help="Check the link speed and width of a specific PCIe device.",
    )
    parser_check_speed.add_argument(
        "-s",
        "--slot",
        required=True,
        help="The PCIe slot BDF identifier (e.g., 01:00.0).",
    )
    parser_check_speed.add_argument(
        "--force",
        action="store_true",
        help=(
            "Fail if device does not report LnkCap/LnkSta "
            "(normally skipped)."
        ),
    )
    parser_check_speed.set_defaults(
        func=lambda args, tester: tester.check_link_state(
            args.slot, force=args.force
        )
    )

    # 'check_aspm' command
    parser_check_aspm = subparsers.add_parser(
        "check_aspm", help="Check the ASPM state of a specific PCIe device."
    )
    parser_check_aspm.add_argument(
        "-s",
        "--slot",
        required=True,
        help="The PCIe slot BDF identifier (e.g., 01:00.0).",
    )
    parser_check_aspm.add_argument(
        "--force",
        action="store_true",
        help=("Fail if device does not support ASPM " "(normally skipped)."),
    )
    parser_check_aspm.set_defaults(
        func=lambda args, tester: tester.check_aspm_state(
            args.slot, force=args.force
        )
    )

    args = parser.parse_args()
    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    tester = PCIeTester()
    # The return value from the function will be our exit code
    sys.exit(args.func(args, tester))


if __name__ == "__main__":
    main()
