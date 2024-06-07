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
import shlex
import os
import re

from checkbox_support.snap_utils.system import on_ubuntucore
from checkbox_support.snap_utils.system import get_series
from checkbox_support.scripts.image_checker import get_source


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
        "--check_time",
        action="store_true",
        help="Check if watchdog service timeout is configured correctly",
    )
    group.add_argument(
        "-s",
        "--check-service",
        action="store_true",
        help="Check if watchdog service is running",
    )
    group.add_argument(
        "-d",
        "--detect",
        action="store_true",
        help="Check if there is watchdog under the /sys/class/watchdog/ "
        "and no other type of watchdog is detected",
    )
    group.add_argument(
        "--set-timeout",
        nargs="?",
        const=35,
        type=int,
        help="Set the timeout for watchdog service",
    )
    group.add_argument(
        "--revert-timeout",
        nargs="?",
        const=35,
        type=int,
        help="Revert the timeout for watchdog service",
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
    ubuntu_version: int = int(get_series().split(".")[0])
    runtime_watchdog_usec: str = get_systemd_wdt_usec()
    is_systemd_wdt_configured: bool = runtime_watchdog_usec != "0"

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


def detect() -> None:
    """
    Detects watchdog under /sys/class/watchdog/ and no other type of watchdog.

    This function executes the watchdog detection process based on the image
    source. For OEM images, it runs the `udev_resource.py` script with the
    argument "-f WATCHDOG". For stock images, it checks if the environment
    variables "WATCHDOG_TYPE" and "WATCHDOG_IDENTITY" are set. It then iterates
    over the watchdog devices under "/sys/class/watchdog/", verifies their
    identities, and raises an exception if an unmatched watchdog is found.

    Raises:
        SystemExit: When the image source is not recognized or when the
        environment variables "WATCHDOG_TYPE" or "WATCHDOG_IDENTITY" are not
        set for stock images.
    """
    # Get the image source
    source = get_source()

    # Handle OEM image source
    if source == "oem":
        cmd = "udev_resource.py -f WATCHDOG"
        result = subprocess.run(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            text=True,
        )
        if result.returncode:
            raise SystemExit("[ERROR] {}".format(result.stderr.strip()))
        print(result.stdout.strip())

    # Handle stock image source
    elif source == "stock":
        # Check if environment variables are set
        if (
            "WATCHDOG_TYPE" not in os.environ
            or "WATCHDOG_IDENTITY" not in os.environ
        ):
            raise SystemExit(
                "WATCHDOG_TYPE or WATCHDOG_IDENTITY not set!\n"
                "Please define the WATCHDOG_TYPE and WATCHDOG_IDENTITY "
                "in advance!"
            )
        input_identities = os.environ["WATCHDOG_IDENTITY"].split(",")

        # Iterate over watchdog devices
        watchdogs = os.listdir("/sys/class/watchdog")
        for watchdog in watchdogs:
            if not watchdog.startswith("watchdog"):
                continue

            # Get the identity of the watchdog
            path = "/sys/class/watchdog/{}/identity".format(watchdog)
            with open(path, "r") as f:
                identity = f.readline().strip()
                print("Identity of {}: {}".format(path, identity))
                try:
                    # check that the identity was expected
                    input_identities.remove(identity)
                    print("Identity of {}: {}".format(path, identity))
                # Check if the identity matches the expected identity
                except KeyError:
                    raise SystemExit(
                        "Found an unmatched watchdog!\n"
                        "Expected: {}\n"
                        "Found: {}".format(
                            os.environ["WATCHDOG_IDENTITY"], identity
                        )
                    )

    # Handle unrecognized image source
    else:
        raise SystemExit("Unrecognized image source: {}".format(source))


def set_timeout(timeout: int = 35) -> None:
    """
    Sets the watchdog timeout in /etc/systemd/system.conf
    and reloads configuration.

    Args:
        timeout (int): Timeout value in seconds. Default is 35.

    Raises:
        SystemExit: If there is an error in reloading the configuration.
    """
    # Pattern to match the line containing the current watchdog timeout
    pattern = r".?RuntimeWatchdogSec=.*"

    # Read the contents of /etc/systemd/system.conf
    with open("/etc/systemd/system.conf", "r") as f:
        text = f.read()

        # Check if the timeout is already set
        if not re.search(pattern, text):
            raise SystemExit("Watchdog timeout is already set")

        # Substitute the current timeout with the new one
        text = re.sub(
            pattern,
            "RuntimeWatchdogSec={}".format(timeout),
            text,
            flags=re.MULTILINE,
        )

    print("Configuring Watchdog timeout...")
    # Write the updated configuration to /etc/systemd/system.conf
    with open("/etc/systemd/system.conf", "w") as f:
        f.write(text)

    print("Reloading configuration...")
    # Reload the configuration
    cmd = "systemctl daemon-reexec"
    res = subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Raise an error if there was an error in reloading the configuration
    if res.returncode:
        raise SystemExit("[ERROR] {}".format(res.stderr.strip()))

    # Print the new timeout value
    print("Watchdog timeout is now set to {}".format(timeout))


def revert_timeout(timeout: int = 35) -> None:
    """
    Revert the watchdog timeout to 0 in /etc/systemd/system.conf
    and reload the configuration.

    Args:
        timeout (int): The timeout value to revert to. Default is 35.

    Raises:
        SystemExit: If the timeout pattern is not found in the
        configuration file or if there is an error in reloading the
        configuration.
    """
    # Pattern to match the line containing the current watchdog timeout
    pattern = "RuntimeWatchdogSec={}".format(timeout)

    # Read the contents of /etc/systemd/system.conf
    with open("/etc/systemd/system.conf", "r") as f:
        text = f.read()

        # Check if the timeout is already set
        if not re.search(pattern, text):
            raise SystemExit(
                "Could not find Watchdog timeout equal to "
                "{} in /etc/systemd/system.conf".format(timeout)
            )

        # Substitute the current timeout with 0
        text = re.sub(
            pattern,
            "#RuntimeWatchdogSec=0",
            text,
            flags=re.MULTILINE,
        )

    print("Configuring Watchdog timeout...")
    # Write the updated configuration to /etc/systemd/system.conf
    with open("/etc/systemd/system.conf", "w") as f:
        f.write(text)

    print("Reloading configuration...")
    # Reload the configuration
    cmd = "systemctl daemon-reexec"
    res = subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Raise an error if there was an error in reloading the configuration
    if res.returncode:
        raise SystemExit("[ERROR] {}".format(res.stderr.strip()))

    # Print the new timeout value
    print("Watchdog timeout is now set to 0 and disabled")


def main():
    args = watchdog_argparse()
    if args.check_time:
        check_timeout()
    elif args.check_service:
        check_service()
    elif args.detect:
        detect()
    elif args.set_timeout:
        set_timeout(args.set_timeout)
    elif args.revert_timeout:
        revert_timeout(args.revert_timeout)
    else:
        raise SystemExit("Unexpected arguments")


if __name__ == "__main__":
    main()
