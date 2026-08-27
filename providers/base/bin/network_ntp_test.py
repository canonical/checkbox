#!/usr/bin/env python3
"""
Program to test syncing the clock with an internet time server via
SNTP UDP query.

Copyright (C) 2010-2026 Canonical Ltd.

Authors:
    Jeff Lane <jeffrey.lane@canonical.com>
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

The purpose of this script is to test whether the test system can
connect to an internet time server and sync the local clock via a native
SNTP UDP query.

It checks for active time daemons and temporarily stops them
during the test to prevent background interference.

By default, we're hitting ntp.ubuntu.com, however you can use any valid NTP
server by passing the URL to the program via --server

"""

import sys
import os
import logging
import time
import socket
import struct
import subprocess
from argparse import ArgumentParser

NTP_UNIX_OFFSET = 2208988800


def ManageTimeDaemon(action, stopped_daemon=None):
    """
    Checks to see if any time daemons are running, and stops them if they are.
    If the action is "start", it will restart any daemons that were stopped.
    """
    daemons_to_check = ["systemd-timesyncd", "ntpd", "chronyd"]
    checked_daemons = []

    try:
        if action == "stop":
            for daemon in daemons_to_check:
                check = subprocess.run(
                    ["systemctl", "is-active", daemon],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if check.returncode == 0:
                    logging.info("Stopping %s..." % daemon)
                    subprocess.run(
                        ["systemctl", "stop", daemon],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    checked_daemons.append(daemon)
            return checked_daemons
        elif action == "start" and stopped_daemon:
            for daemon in stopped_daemon:
                logging.info("Starting %s..." % daemon)
                subprocess.run(
                    ["systemctl", "start", daemon],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return []

    except Exception as e:
        logging.error("Failed to manage time daemon: %s" % e)

    return []


def SyncTime(server):
    """
    Syncs time via native SNTP query to the specified ntp server.
    It avoids ntpdate Snap dependency issues.
    """
    logging.debug("Querying NTP server %s via native UDP socket..." % server)
    ntp_packet = b"\x1b" + 47 * b"\x00"

    try:
        res = socket.getaddrinfo(
            server, 123, socket.AF_UNSPEC, socket.SOCK_DGRAM
        )
        af, socktype, proto, _, sa = res[0]
        with socket.socket(af, socktype, proto) as s:
            s.settimeout(10)
            s.sendto(ntp_packet, sa)
            data, _ = s.recvfrom(1024)

        if data and len(data) >= 48:
            # Unpack the transmit timestamp and conver to Unix time
            seconds, fraction = struct.unpack("!II", data[40:48])
            unix_time = (seconds - NTP_UNIX_OFFSET) + (fraction / (2**32))
            # Set the system time
            time.clock_settime(time.CLOCK_REALTIME, unix_time)
            logging.info(
                "NTP server %s responded with time: %s"
                % (server, time.ctime(unix_time))
            )
            return True

        logging.error("Invalid response from NTP server %s" % server)

    except Exception as e:
        logging.error(
            "Failed to sync time with NTP server %s: %s" % (server, e)
        )

    return False


def TimeCheck():
    """
    Returns current time in a time.localtime() struct
    """
    return time.localtime()


def SkewTime():
    """
    Optional function. We can skew time by 1 hour if we'd like to see real sync
    changes being enforced
    """
    TIME_SKEW = 1
    logging.info("Time Skewing has been selected. Setting clock ahead 1 hour")
    logging.info("Current time is: %s" % time.asctime())

    skewed = time.time() + TIME_SKEW * 3600
    time.clock_settime(time.CLOCK_REALTIME, skewed)

    logging.info("Pre-sync time is: %s" % time.asctime())


def main():
    description = (
        "Tests the ability to skew and sync the clock with an NTP server"
    )
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--server",
        action="store",
        default="ntp.ubuntu.com",
        help="The NTP server to sync from. The default server \
                        is %(default)s",
    )
    parser.add_argument(
        "--skew-time",
        action="store_true",
        default=False,
        help="Setting this will change system time ahead by 1 \
                        hour to make the results of ntp syncing more dramatic \
                        and noticeable.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Verbose output for debugging purposes",
    )
    args = parser.parse_args()

    if os.geteuid() != 0:
        parser.error("You must run this script as root")

    # Set up logging
    format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(format, date_format))
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    stopped_daemons = ManageTimeDaemon("stop")

    try:
        # Time skew check
        if args.skew_time:
            logging.debug("Setting system time ahead one hour")
            SkewTime()
        else:
            logging.info("Pre-sync time is: %s" % time.asctime(TimeCheck()))

        # Perform sync test
        sync = SyncTime(args.server)

        logging.info("Current system time is: %s" % time.asctime(TimeCheck()))

    finally:
        ManageTimeDaemon("start", stopped_daemons)

    return 0 if sync else 1


if __name__ == "__main__":
    sys.exit(main())
