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
import shlex
import logging
import subprocess
from checkbox_support.snap_utils.snapd import Snapd


def get_fwupdmgr_services_versions():
    """Show fwupd client and daemon versions

    Returns:
        list: fwupd client and daemon versions
    """
    fwupd_vers = subprocess.run(
        shlex.split("fwupdmgr --version --json"),
        capture_output=True)
    fwupd_vers = json.loads(fwupd_vers.stdout).get("Versions", [])

    return fwupd_vers


def get_fwupd_runtime_version():
    """Get fwupd runtime version

    Returns:
        tuple: fwupd runtime version
    """
    runtime_ver = ()

    for ver in get_fwupdmgr_services_versions():
        if (ver.get("Type") == "runtime" and
                ver.get("AppstreamId") == "org.freedesktop.fwupd"):
            runtime_ver = tuple(map(int, ver.get("Version").split(".")))

    return runtime_ver


def get_firmware_info_fwupd():
    """
    Dump firmware information for all devices detected by fwupd
    """
    if Snapd().list("fwupd"):
        # Dump firmware info by fwupd snap
        subprocess.run(shlex.split("fwupd.fwupdmgr get-devices --json"))
    else:
        # Dump firmware info by fwupd debian package
        runtime_ver = get_fwupd_runtime_version()
        # Apply workaround to unset the SNAP for the fwupd issue
        # See details from following PR
        # https://github.com/canonical/checkbox/pull/1089

        # SNAP environ is avaialble, so it's running on checkbox snap
        # Unset the environ variable if debian fwupd lower than 1.9.14
        if os.environ.get("SNAP") and runtime_ver < (1, 9, 14):
            del os.environ["SNAP"]

        subprocess.run(shlex.split("fwupdmgr get-devices --json"))


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

    try:
        get_firmware_info_fwupd()
    except Exception as err:
        logging.error(err)
