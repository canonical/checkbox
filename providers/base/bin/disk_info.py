#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright (C) 2010-2013 by Cloud Computing Center for Mobile Applications
# Industrial Technology Research Institute
# Copyright 2016-2025 Canonical Ltd.
#
# Authors:
#   Nelson Chu <Nelson.Chu@itri.org.tw>
#   Jeff Lane <jeff@ubuntu.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
"""disk_info utility."""

import json
import re
import sys
from subprocess import check_output, CalledProcessError

from checkbox_support.parsers.udevadm import find_pkname_is_root_mountpoint


def get_lsblk_json():
    lsblk = check_output(
        [
            "lsblk",
            "-i",
            "-n",
            "--json",
            "-o",
            "KNAME,TYPE,SIZE,MODEL,MOUNTPOINT",
        ],
        universal_newlines=True,
    )
    return json.loads(lsblk)


def main(lsblk):
    """
    disk_info.

    Uses lsblk to gather information about disks seen by the OS.
    Outputs kernel name, model and size data
    """
    disks = 0
    for blkdev in lsblk.get("blockdevices", []):
        if blkdev["type"] not in ("disk", "crypt"):
            continue
        # Only consider MMC block devices if one of their mounted partitions is
        # root (/)
        if blkdev["kname"].startswith(
            "mmcblk"
        ) and not find_pkname_is_root_mountpoint(blkdev["kname"], lsblk):
            continue
        # Don't consider any block dev mounted as snapd save partition
        if blkdev["mountpoint"] and "snapd/save" in blkdev["mountpoint"]:
            continue
        disks += 1
        model = blkdev["model"]
        if not model:
            model = "Unknown"
        print("Name: /dev/{}".format(blkdev["kname"]))
        print("\t{:7}\t{}".format("Model:", model))
        print("\t{:7}\t{}".format("Size:", blkdev["size"]))
    if not disks:
        raise SystemExit("No disk information discovered.")


if __name__ == "__main__":
    lsblk = get_lsblk_json()
    sys.exit(main(lsblk))
