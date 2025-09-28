#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Eugene Wu <eugene.wu@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import subprocess
import datetime
import re
import argparse
import logging
import sys


def get_timestamp(file):
    with open(file, "r") as f:
        saved_timestamp = float(f.read())
    readable_start_time = datetime.datetime.fromtimestamp(saved_timestamp)
    logging.debug("Test started at: {}".format(readable_start_time))
    return saved_timestamp


def extract_timestamp(log_line):
    pattern = r"(\d+\.\d+)"
    match = re.search(pattern, log_line)
    return float(match.group(1)) if match else None


def get_wakeup_timestamp():
    # Get the time stamp of the system resume from suspend for s3
    command = ["journalctl", "-b", "0", "--output=short-unix"]
    result = subprocess.check_output(
        command, shell=False, universal_newlines=True
    )
    logs = result.splitlines()

    for log in reversed(logs):
        if r"suspend exit" in log:
            logging.debug(log)
            latest_system_back_time = extract_timestamp(log)
            readable_back_time = datetime.datetime.fromtimestamp(
                latest_system_back_time
            )
            logging.debug("System back time: {}".format(readable_back_time))
            return latest_system_back_time

    return None


def get_system_boot_time():
    """
    Read btime from /proc/stat and
    return the system boot timestamp (Unix timestamp, in seconds).
    """
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("btime"):
                    btime = float(line.split()[1])
                    back_time = datetime.datetime.fromtimestamp(btime)
                    logging.debug("System back time: {}".format(back_time))
                    return btime
        logging.error("cannot find btime")
        return None
    except FileNotFoundError:
        logging.error("cannot open /proc/stat.")
        return None
    except Exception as e:
        logging.error("error while read btime: {}".format(e))
        return None


def parse_args(args=sys.argv[1:]):
    """
    command line arguments parsing

    :param args: arguments from sys
    :type args: sys.argv
    """
    parser = argparse.ArgumentParser(
        description="Parse command line arguments."
    )

    parser.add_argument("--powertype", type=str, help="Waked from s3 or s5.")
    parser.add_argument(
        "--timestamp_file",
        type=str,
        help="The file to store the timestamp of test start.",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=60,
        help="Delay between attempts (in seconds).",
    )
    parser.add_argument(
        "--retry", type=int, default=3, help="Number of retry attempts."
    )

    return parser.parse_args(args)


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format="%(levelname)s: %(message)s",
    )

    logging.info("wake-on-LAN check test started.")

    powertype = args.powertype
    timestamp_file = args.timestamp_file
    delay = args.delay
    max_retries = args.retry

    logging.info("PowerType: {}".format(powertype))

    test_start_time = get_timestamp(timestamp_file)
    if test_start_time is None:
        raise SystemExit(
            "Couldn't get the test start time from timestamp file."
        )

    system_back_time = (
        get_wakeup_timestamp() if powertype == "s3" else get_system_boot_time()
    )
    if system_back_time is None:
        raise SystemExit("Couldn't get system back time.")

    time_difference = system_back_time - test_start_time
    logging.debug("time difference: {} seconds".format(time_difference))

    # system_back_time - test_start_time > 1.5*max_retries*delay which meanse
    # the system was bring up by rtc other than Wake-on-LAN
    expect_time_range = 1.5 * max_retries * delay
    if time_difference > expect_time_range:
        raise SystemExit(
            "The system took much longer than expected to wake up,"
            " and it wasn't awakened by wake-on-LAN."
        )
    elif time_difference < 0:
        raise SystemExit("System resumed earlier than expected.")
    else:
        logging.info("wake-on-LAN works well.")
        return True


if __name__ == "__main__":
    main()
