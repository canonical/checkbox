#!/usr/bin/env python3
"""
Test system clock synchronization using chrony.

The test records the current time, moves the system clock one hour into the
past using chrony's manual time input, and verifies that chrony can restore
the correct time from its configured NTP sources. It uses the system's chrony
configuration instead of contacting a hard-coded NTP server.

The chrony service must already be running before the test starts.

Copyright (C) 2026 Canonical Ltd.

Author:
    Jason Leonhard <jason.leonhard@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import logging
import os
import subprocess as sp
import sys
import time

DEFAULT_TIMEOUT = 60
TIME_SKEW_SECONDS = 60 * 60  # 1 hour

logger = logging.getLogger(__name__)


def is_chrony_active() -> bool:
    """Return whether the chrony service is currently active."""
    result = sp.run(["systemctl", "is-active", "--quiet", "chrony.service"])
    return result.returncode == 0


def skew_time(current_time: float) -> None:
    """Skew the system time by one hour into the past."""
    skewed_time = current_time - TIME_SKEW_SECONDS
    formatted_skewed_time = time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime(skewed_time)
    )

    # Enables use of the settime command
    sp.check_output(["chronyc", "manual", "on"], stderr=sp.STDOUT, text=True)
    try:
        # Set the system time to the skewed value
        sp.check_output(
            ["chronyc", "settime", formatted_skewed_time],
            stderr=sp.STDOUT,
            text=True,
        )
        sp.check_output(
            ["chronyc", "-a", "makestep"], stderr=sp.STDOUT, text=True
        )
    finally:
        try:
            # Reset the manual time adjustment
            sp.check_output(
                ["chronyc", "manual", "reset"], stderr=sp.STDOUT, text=True
            )
        finally:
            # Disables use of the settime command
            sp.check_output(
                ["chronyc", "manual", "off"], stderr=sp.STDOUT, text=True
            )


def sync_with_chrony(timeout: int) -> None:
    """Synchronize the system clock with chrony."""
    # Re-enable the configured NTP sources.
    sp.check_output(["chronyc", "online"], stderr=sp.STDOUT, text=True)
    # Step the clock if the next update has an offset over 0.1 seconds.
    sp.check_output(
        ["chronyc", "makestep", "0.1", "1"], stderr=sp.STDOUT, text=True
    )
    # Request one good measurement, with at most four attempts per source.
    sp.check_output(["chronyc", "burst", "1/4"], stderr=sp.STDOUT, text=True)
    # Check once per second, for up to timeout attempts, until synchronized.
    logger.info("Waiting up to %s seconds for synchronization", timeout)
    sp.check_output(
        ["chronyc", "waitsync", str(timeout), "0.1", "0.0", "1"],
        stderr=sp.STDOUT,
        text=True,
        timeout=timeout,
    )


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize the local clock using chrony"
    )
    parser.add_argument(
        "--timeout",
        default=DEFAULT_TIMEOUT,
        type=int,
        help="maximum number of seconds to wait for synchronization",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Verbose output for debugging purposes",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG if args.debug else logging.INFO,
    )

    if os.geteuid() != 0:
        logger.error("You must run this script as root")
        return 1

    if not is_chrony_active():
        logger.error("Chrony service is not active")
        return 1

    try:
        # Record the correct time before deliberately changing the clock.
        current_time = time.time()
        current_datetime = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(current_time)
        )
        logger.info("Current system date and time: %s", current_datetime)

        # Move the clock back one hour and apply the change.
        skew_time(current_time)
        skewed_datetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.info("Skewed system date and time: %s", skewed_datetime)

        # Synchronize from NTP and confirm the clock returned to real time.
        sync_with_chrony(args.timeout)

        # Verify that the system time is now correct.
        synchronized_time = time.time()
        if synchronized_time < current_time:
            raise RuntimeError("Failed to synchronize the system time")
        synchronized_datetime = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(synchronized_time)
        )
        logger.info(
            "Synchronized system date and time: %s", synchronized_datetime
        )
    except sp.CalledProcessError as error:
        logger.error(
            "Time synchronization failed: %s",
            error.output.strip() if error.output else error,
        )
        return 1
    except (OSError, RuntimeError, sp.SubprocessError) as error:
        logger.error("Time synchronization failed: %s", error)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
