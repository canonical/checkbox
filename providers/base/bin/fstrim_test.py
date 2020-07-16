#!/usr/bin/env python3

# Test fstrim functionality on a disk device
#
# Copyright (C) 2020 Canonical Ltd.
#
# Authors:
#  Rod Smith <rod.smith@canonical.com>
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
#
"""
This script checks to see if a block device supports TRIM via a call to the
fstrim utility. This requires ensuring that a Linux partition on the target
device be mounted, so this script does this, if necessary.

The script returns 0 on success and 1 on failure, with output
via Python logging about the nature of the success/failure.
"""


import logging
import shlex
import sys
from argparse import ArgumentParser
from subprocess import (
    PIPE,
    Popen
)
from checkbox_support.disk_support import Disk


def mount_filesystem(device):
    if "/dev" not in device and device != "":
        device = "/dev/" + device

    test_disk = Disk(device)
    mount_point = None
    if test_disk.mount_filesystem(False):
        mount_point = test_disk.get_mount_point()
        logging.info("mount point is {}".format(test_disk.get_mount_point()))
    if not mount_point:
        logging.error("Test failed; {} is not mounted!".format(device))

    return mount_point


def run_fstrim(device):
    mount_point = mount_filesystem(device)
    if mount_point is not None:
        command = "fstrim -v {}".format(mount_point)
        triminfo = Popen(shlex.split(command), stdout=PIPE)
        lsbinfo_bytes = triminfo.communicate()[0]
        lsbinfo = lsbinfo_bytes.decode(encoding="utf-8",
                                       errors="ignore").rstrip()
        logging.info(lsbinfo)
        retval = triminfo.returncode
    else:
        retval = 1
    return retval


def main():
    parser = ArgumentParser()
    parser.add_argument('--device-file', default="sda",
                        help='The file within /dev that maps to the device')
    args = parser.parse_args()
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    retval = run_fstrim(args.device_file)

    return retval


if __name__ == '__main__':
    sys.exit(main())
