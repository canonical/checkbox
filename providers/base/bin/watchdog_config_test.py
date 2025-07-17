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

import argparse
import subprocess

from checkbox_support.snap_utils.system import on_ubuntucore
from checkbox_support.snap_utils.system import get_series


def get_systemd_wdt_usec():
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


def watchdog_service_check():
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
            print(
                "systemd watchdog should be enabled but reset timeout "
                "(RuntimeWatchdogUSec) is set to: "
                "{}".format(runtime_watchdog_usec)
            )
            print(
                "In order for the systemd watchdog to work, "
                "the RuntimeWatchdogUSec configuration option must be set "
                "before running this test."
            )
            raise SystemExit(1)
        print(
            "systemd watchdog enabled, reset timeout: {}".format(
                runtime_watchdog_usec
            )
        )
    else:
        if is_systemd_wdt_configured:
            print(
                "systemd watchdog should not be enabled but reset timeout "
                "(RuntimeWatchdogUSec) is set to: "
                "{}".format(runtime_watchdog_usec)
            )
            print(
                "In order for the watchdog.service to work, "
                "the RuntimeWatchdogUSec configuration option must be 0 "
                "before running this test."
            )
            raise SystemExit(1)
        print(
            "systemd watchdog disabled, reset timeout: {}".format(
                runtime_watchdog_usec
            )
        )


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


USAGE = """
Watchdog Config Test Scripts

Usage:
  watchdo_config_test.py check-time
  watchdo_config_test.py check-service

Commands:
  check-time     Check if systemd watchdog timeout is configured correctly
  check-service  Check if watchdog.service is configured correctly

Note:
  On Ubuntu Core and Ubuntu 20.04 or later, the system no longer requires
  the separate watchdog service. Instead, watchdog support is now integrated
  and managed directly through the systemd watchdog mechanism.

  On Ubuntu 18.04 and earlier, watchdog support rely on the separate
  watchdog service.
"""

def watchdog_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Watchdog Testing Tool",
        description="This is a tool to help you perform the watchdog testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        usage=USAGE,
    )
    parser.add_argument(
        "test",
        type=str,
        choices=["check-timeout", "check-service"],
        help="abd",
    )

    return parser.parse_args()


def main():
    args = watchdog_argparse()
    if args.test == "check-timeout":
        check_timeout()
    elif args.test == "check-service":
        check_service()
    else:
        raise SystemExit("Unexpected arguments")


if __name__ == "__main__":
    main()
