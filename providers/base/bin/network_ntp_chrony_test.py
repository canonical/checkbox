#!/usr/bin/env python3
"""
Test system clock synchronization using chrony.

The test records the current time, moves the system clock one hour into the
past using chrony's manual time input, and verifies that chrony can restore
the correct time from its configured NTP sources. It uses the system's chrony
configuration instead of contacting a hard-coded NTP server.

The original chrony service state is restored after the test.

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
import subprocess
import sys

DEFAULT_TIMEOUT = 60
TIME_SKEW_SECONDS = 60 * 60  # 1 hour


def run_command(command, timeout=None, check=True):
    """Run a command and raise an error when it fails."""
    logging.debug("Running: %s", " ".join(command))
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )
    if check and result.returncode:
        error = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError("{}: {}".format(" ".join(command), error))
    return result


def is_chrony_active():
    """Return whether the chrony service is currently active."""
    result = run_command(
        ["systemctl", "is-active", "--quiet", "chrony.service"],
        check=False,
    )
    return result.returncode == 0


def skew_time(current_time):
    """Skew the system time by one hour into the past."""
    skewed_time = current_time - TIME_SKEW_SECONDS
    formatted_skewed_time = run_command(
        [
            "date",
            "--date=@{}".format(skewed_time),
            "+%Y-%m-%d %H:%M:%S",
        ]
    ).stdout.strip()

    run_command(["chronyc", "manual", "on"])
    try:
        run_command(["chronyc", "settime", formatted_skewed_time])
        run_command(["chronyc", "-a", "makestep"])
    finally:
        run_command(["chronyc", "manual", "reset"])
        run_command(["chronyc", "manual", "off"])


def sync_with_chrony(timeout):
    """Synchronize the system clock with chrony."""
    # Re-enable the configured NTP sources.
    run_command(["chronyc", "online"])
    # Step the clock if the next update has an offset over 0.1 seconds.
    run_command(["chronyc", "makestep", "0.1", "1"])
    # Request one good measurement, with at most four attempts per source.
    run_command(["chronyc", "burst", "1/4"])
    # Check once per second, for up to timeout attempts, until synchronized.
    run_command(
        ["chronyc", "waitsync", str(timeout), "0.1", "0.0", "1"],
        timeout=timeout,
    )


def parse_args(argv=None):
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


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG if args.debug else logging.INFO,
    )

    if os.geteuid() != 0:
        logging.error("You must run this script as root")
        return 1

    try:
        # Preserve the service state so the test does not change the system.
        was_active = is_chrony_active()
        if not was_active:
            run_command(["systemctl", "start", "chrony.service"])

        try:
            # Record the correct time before deliberately changing the clock.
            current_time = int(run_command(["date", "+%s"]).stdout.strip())
            current_datetime = run_command(
                ["date", "+%Y-%m-%d %H:%M:%S"]
            ).stdout.strip()
            logging.info("Current system date and time: %s", current_datetime)

            # Move the clock back one hour and apply the change.
            skew_time(current_time)

            skewed_datetime = run_command(
                ["date", "+%Y-%m-%d %H:%M:%S"]
            ).stdout.strip()
            logging.info("Skewed system date and time: %s", skewed_datetime)

            # Synchronize from NTP and confirm the clock returned to real time.
            sync_with_chrony(args.timeout)

            synchronized_time = int(
                run_command(["date", "+%s"]).stdout.strip()
            )
            if synchronized_time < current_time:
                raise RuntimeError("Failed to synchronize the system time")
            synchronized_datetime = run_command(
                ["date", "+%Y-%m-%d %H:%M:%S"]
            ).stdout.strip()
            logging.info(
                "Synchronized system date and time: %s",
                synchronized_datetime,
            )
        finally:
            # Restore the service state found before the test.
            if not was_active:
                run_command(["systemctl", "stop", "chrony.service"])
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        logging.error("Time synchronization failed: %s", error)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
