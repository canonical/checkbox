#!/usr/bin/env python3
"""
Enable custom TDX kernel and qemu to run TDX
This is a tech preview
Copyright (C) 2024 Canonical Ltd.

Authors
    Michael Reed <michael.reed@canonical.com.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import sys
import subprocess

checkbox_tests = [
    "checkbox-tdx.test-runner-automated",
    "checkbox-tdx.test-runner-automated-boot",
    "checkbox-tdx.test-runner-automated-guest",
    "checkbox-tdx.test-runner-automated-host",
    "checkbox-tdx.test-runner-automated-perf",
    "checkbox-tdx.test-runner-automated-quote",
    "checkbox-tdx.test-runner-automated-stress"
    ]

logger = logging.getLogger(__name__)


def run(cmd: str) -> tuple[bool, str]:
    """Run command and return (success, stdout)."""
    try:
        logger.debug("Command: %s", cmd)
        out = subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
        )
        logger.debug("STDOUT: %s", out)
        return True, out
    except subprocess.CalledProcessError as e:
        logger.error("Command failed: %s", cmd)
        logger.info("STDOUT: %s", e.stdout)
        return False, e.stdout


def main():
    # Check for TDX kernel
    cmd1 = "uname -r | grep intel"
    status, output = run(cmd1)
    if status:
        logger.info("TDX kernel is installed and running")
        logger.info("Output: %s", output)
        print("TDX kernel is installed and running")
        print("Output: %s", output)
    else:
        logger.error("TDX kernel is not installed,run setup-tdx-host.sh")
        print("TDX kernel is not installed, run setup-tdx-host.sh")
        sys.exit(1)

    # Check for TDX
    cmd1 = "sudo dmesg | grep \"tdx: module initialized\""
    status, output = run(cmd1)
    if status:
        logger.info("TDX is installed")
        logger.info("Output: %s", output)
        print("TDX is installed")
        print("Output: %s", output)
    else:
        logger.error("TDX is not enabled in the BIOS or not installed")
        print("TDX is not enabled in the BIOS or not installed")
        sys.exit(1)

    # Check for checkbox-tdx
    cmd1 = "snap list | grep checkbox24"
    cmd2 = "snap list | grep checkbox-tdx"

    status1, output = run(cmd1)
    status2, output = run(cmd2)

    if not (status1) and not (status2):
        # Attempt to install checkbox-tdx if it is not installed
        logger.info("Install checkbox-tdx")
        print("Install checkbox-tdx")
        cmd1 = "sudo snap install checkbox24"
        cmd2 = "sudo snap install --edge checkbox-tdx --classic"
        status1, output = run(cmd1)
        status2, output = run(cmd2)

    if(status1) and (status2):
        print("The following launchers will run tdx tests")
        logger.info("The following launchers will run tdx tests")
        for test in checkbox_tests:
            logger.info(test)
            print(test)
    else:
        print("checkbox-tdx launchers are not installed")
        logger.error("checkbox-tdx launchers are not installed")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
