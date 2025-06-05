#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Vic Liu <vic.liu@canonical.com>
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
Watchdog implementation on both classic and core image no longer rely
on watchdogd service since 20.04, with this change watchdog/systemd-config
tests only systemd configuration on 20.04 and later series while keeping
the original test for prior releases
"""

import subprocess
import argparse

from checkbox_support.snap_utils.system import on_ubuntucore
from checkbox_support.snap_utils.system import get_series


def watchdog_argparse() -> argparse.Namespace:
    """
    Parse command line arguments and return the parsed arguments.

    This function parses the command line arguments and returns the parsed
    arguments. The arguments are parsed using the `argparse` module. The
    function takes no parameters.

    Returns:
        argparse.Namespace: The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        prog="Watchdog Testing Tool",
        description="This is a tool to help you perform the watchdog testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-t",
        "--check-time",
        action="store_true",
        help="Check if watchdog service timeout is configured correctly",
    )
    group.add_argument(
        "-s",
        "--check-service",
        action="store_true",
        help="Check if watchdog service is running",
    )
    return parser.parse_args()


def get_systemd_wdt_usec() -> str:
    """
    Return value of systemd-watchdog RuntimeWatchdogUSec
    """
    cmd = ["systemctl", "show", "-p", "RuntimeWatchdogUSec"]
    try:
        result = subprocess.check_output(cmd, universal_newlines=True)
    except Exception as err:
        raise SystemExit("Error: {}".format(err))

    if result:
        runtime_watchdog_usec = result.split("=")[1].strip()
        return runtime_watchdog_usec
    else:
        raise SystemExit(
            "Unexpected failure occurred when executing: {}".format(cmd)
        )


def watchdog_service_check() -> bool:
    """
    Check if the watchdog service is configured correctly
    """
    cmd = ["systemctl", "is-active", "watchdog.service", "--quiet"]
    try:
        return not subprocess.run(cmd).returncode
    except Exception as err:
        raise SystemExit("Error: {}".format(err))


def check_timeout() -> bool:
    ubuntu_version = int(get_series().split(".")[0])
    runtime_watchdog_usec = get_systemd_wdt_usec()
    is_systemd_wdt_configured = runtime_watchdog_usec != "0"

    if ubuntu_version >= 20 or on_ubuntucore():
        if not is_systemd_wdt_configured:
            raise SystemExit(
                "systemd watchdog should be enabled but reset timeout: "
                "{}".format(runtime_watchdog_usec)
            )
        print(
            "systemd watchdog enabled, reset timeout: {}".format(
                runtime_watchdog_usec
            )
        )
    else:
        if is_systemd_wdt_configured:
            raise SystemExit(
                "systemd watchdog should not be enabled but "
                "reset timeout: {}".format(runtime_watchdog_usec)
            )
        print("systemd watchdog disabled")


def check_service() -> bool:
    ubuntu_version = int(get_series().split(".")[0])
    is_wdt_service_configured = watchdog_service_check()

    if ubuntu_version >= 20 or on_ubuntucore():
        if is_wdt_service_configured:
            raise SystemExit("Found unexpected active watchdog.service unit")
        print("watchdog.service is not active")
    else:
        if not is_wdt_service_configured:
            raise SystemExit("watchdog.service unit does not report as active")
        print("watchdog.service is active")


def main():
    args = watchdog_argparse()
    if args.check_time:
        check_timeout()
    elif args.check_service:
        check_service()
    else:
        raise SystemExit("Unexpected arguments")


if __name__ == "__main__":
    main()
