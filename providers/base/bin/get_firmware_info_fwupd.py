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

import os
import sys
import json
import logging
import argparse
import subprocess
from checkbox_support.snap_utils.snapd import Snapd


def get_fwupdmgr_services_versions() -> list:
    """Show fwupd client and daemon versions

    Returns:
        list: fwupd client and daemon versions
    """
    fwupd_vers = subprocess.check_output(["fwupdmgr", "--version", "--json"])
    fwupd_vers = json.loads(fwupd_vers).get("Versions", [])

    return fwupd_vers


def get_fwupd_runtime_version() -> tuple:
    """Get fwupd runtime version

    Returns:
        tuple: fwupd runtime version
    """
    runtime_ver = ()

    for ver in get_fwupdmgr_services_versions():
        if (
            ver.get("Type") == "runtime"
            and ver.get("AppstreamId") == "org.freedesktop.fwupd"
        ):
            runtime_ver = tuple(map(int, ver.get("Version").split(".")))

    return runtime_ver


def choose_command() -> str:
    """
    Choose which command should be used
    """
    if Snapd().list("fwupd"):
        return "fwupd.fwupdmgr"
    else:
        return "fwupdmgr"


def get_environment() -> dict:
    """
    Get the environment to use for subprocess execution.
    Apply workaround to unset the SNAP for the fwupd issue.
    See details from following PR
    https://github.com/canonical/checkbox/pull/1089
    """
    env = os.environ.copy()

    # If using debian fwupd (not snap)
    if not Snapd().list("fwupd"):
        runtime_ver = get_fwupd_runtime_version()
        # SNAP environ is available, so it's running on checkbox snap
        # Unset the environ variable if debian fwupd lower than 1.9.14
        if os.environ.get("SNAP") and runtime_ver < (1, 9, 14):
            env.pop("SNAP", None)

    return env


def get_firmware_info_fwupd() -> None:
    """
    Dump firmware information for all devices detected by fwupd
    """
    try:
        output = subprocess.check_output(
            [choose_command(), "get-devices", "--json"], env=get_environment()
        )
        print(output.decode("utf-8"))
    except subprocess.CalledProcessError as e:
        raise SystemExit("fwupdmgr get-devices failed with {}".format(repr(e)))


def get_bios_setting_fwupd() -> None:
    """
    Dump bios setting detected by fwupd
    """
    try:
        output = subprocess.check_output(
            [choose_command(), "get-bios-setting", "--json"],
            env=get_environment(),
        )
        print(output.decode("utf-8"))
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            "fwupdmgr get-bios-setting failed with {}".format(repr(e))
        )


def parse_args(args=sys.argv[1:]) -> argparse.Namespace:
    """
    command line arguments parsing

    :param args: arguments from sys
    :type args: sys.argv
    """
    parser = argparse.ArgumentParser(
        prog="fwupdmgr executor",
        description="Executing fwupdmger in the right environment",
    )

    parser.add_argument(
        "-c",
        "--command",
        type=str,
        default="get-devices",
        help="Command to execute: get-devices or get-bios-setting "
        "(default: get-devices)",
    )
    return parser.parse_args(args)


if __name__ == "__main__":
    args = parse_args()

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

    try:
        if args.command == "get-devices":
            get_firmware_info_fwupd()
        elif args.command == "get-bios-setting":
            get_bios_setting_fwupd()
        else:
            msg = "Command [{}] is not supported".format(args.command)
            logging.error(msg)
            raise SystemExit(msg)
    except Exception as err:
        logging.error(err)
