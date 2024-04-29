#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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
#

import argparse
import random
import subprocess
import sys
import time


def http_connect(
    url, max_attempts: int = 5, initial_delay=1, backoff_factor=2, max_delay=60
):
    """
    Use `wget` to try to connect to `url`. If attempt fails, the next one is
    made after adding a random delay calculated using a backoff and a jitter
    (with a maximum delay of 60 seconds).
    """
    for attempt in range(1, max_attempts + 1):
        print(
            "Trying to connect to {} (attempt {}/{})".format(
                url, attempt, max_attempts
            )
        )
        try:
            subprocess.run(
                [
                    "wget",
                    "-SO",
                    "/dev/null",
                    url,
                ],
                check=True,
            )
            return
        except subprocess.CalledProcessError as exc:
            print("Attempt {} failed: {}".format(attempt, exc))
            print()
            delay = min(initial_delay * (backoff_factor**attempt), max_delay)
            jitter = random.uniform(
                0, delay * 0.5
            )  # Jitter: up to 50% of the delay
            final_delay = delay + jitter
            print(
                "Waiting for {:.2f} seconds before retrying...".format(
                    final_delay
                )
            )
            time.sleep(final_delay)
    raise SystemExit("Failed to connect to {}!".format(url))


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL to try to connect to")
    parser.add_argument(
        "--attempts",
        default="5",
        help="Number of connection attempts (default %(default)s)",
    )
    args = parser.parse_args(args)
    http_connect(args.url, int(args.attempts))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
