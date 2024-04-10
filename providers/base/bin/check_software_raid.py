#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Stanley Huang <stanley.huang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import re
import sys
import logging
import argparse
import shlex
import subprocess
from pathlib import Path
from typing import Dict


class RAIDStats(Dict):
    device = str
    mode = str


def get_md_stat(filename: str = "/proc/mdstat") -> list:
    """
    Parse the information of RAID devices from /dev/mdstat

    Returns:
        raid_stats (list): the RAID information
    """
    pattern = r"^(md[0-9]+) : active ([a-z0-9]+) [a-z0-9 \[\]]+$"
    raid_raw_data = ""
    raid_stats = []

    with Path(filename) as node:
        raid_raw_data = node.read_text().strip("\n")

    for tmp_data in raid_raw_data.split("\n"):
        find_result = re.search(pattern, tmp_data)
        if find_result:
            raid_node = RAIDStats(
                device=find_result.groups()[0], mode=find_result.groups()[1]
            )
            raid_stats.append(raid_node)

    return raid_stats


def dump_raid_info(nodes: list) -> None:
    """
    Display detail information for all of RAID devices

    Args:
        nodes (list): the name of MD devices
    """
    for node in nodes:
        subprocess.run(shlex.split("mdadm -D /dev/{}".format(node)))


def check_raid_mode_test(modes: str) -> None:
    """
    Validate the RAID modes running on the system is expected

    Args:
        modes (str): the expected RAID modes on the system

    Raises:
        ValueError: when if RAID modes are not expected
    """
    expected_modes = modes.strip().split()
    cur_raid_stats = get_md_stat()

    active_mode = [stat["mode"] for stat in cur_raid_stats]
    logging.info("Active RAID mode on the system: %s", active_mode)
    logging.info("Expected RAID mode: %s", expected_modes)

    dump_raid_info([stat["device"] for stat in cur_raid_stats])

    if sorted(expected_modes) == sorted(active_mode):
        logging.info("PASS: RAID mode on the system is expected")
    else:
        raise ValueError("RAID mode on the system is not expected")


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Check RAID stats and compare mode is expected",
    )
    parser.add_argument(
        "--mode",
        required=True,
        type=str,
        help="The RAID mode is enabeld on the running system",
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    args = register_arguments()

    try:
        check_raid_mode_test(args.mode)
    except Exception as err:
        logging.error(err)
