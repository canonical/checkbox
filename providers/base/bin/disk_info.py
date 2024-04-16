#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright (C) 2010-2013 by Cloud Computing Center for Mobile Applications
# Industrial Technology Research Institute
# Copyright 2016 Canonical Ltd.
#
# Authors:
#   Nelson Chu <Nelson.Chu@itri.org.tw>
#   Jeff Lane <jeff@ubuntu.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

import re
import sys
from subprocess import check_output, CalledProcessError

from checkbox_support.parsers.udevadm import find_pkname_is_root_mountpoint


def main():
    """
    disk_info.

    Uses lsblk to gather information about disks seen by the OS.
    Outputs kernel name, model and size data
    """
    pattern = re.compile(
        'KNAME="(?P<KNAME>.*)" '
        'TYPE="(?P<TYPE>.*)" '
        'SIZE="(?P<SIZE>.*)" '
        'MODEL="(?P<MODEL>.*)" '
        'MOUNTPOINT="(?P<MOUNTPOINT>.*)"'
    )
    try:
        lsblk = check_output(
            [
                "lsblk",
                "-i",
                "-n",
                "-P",
                "-o",
                "KNAME,TYPE,SIZE,MODEL,MOUNTPOINT",
            ],
            universal_newlines=True,
        )
    except CalledProcessError as e:
        sys.exit(e)

    disks = 0
    for line in lsblk.splitlines():
        m = pattern.match(line)
        if not m or m.group("TYPE") not in ("disk", "crypt"):
            continue
        # Only consider MMC block devices if one of their mounted partitions is
        # root (/)
        if m.group("KNAME").startswith(
            "mmcblk"
        ) and not find_pkname_is_root_mountpoint(m.group("KNAME"), lsblk):
            continue
        # Don't consider any block dev mounted as snapd save partition
        if "snapd/save" in m.group("MOUNTPOINT"):
            continue
        disks += 1
        model = m.group("MODEL")
        if not model:
            model = "Unknown"
        print("Name: /dev/{}".format(m.group("KNAME")))
        print("\t{:7}\t{}".format("Model:", model))
        print("\t{:7}\t{}".format("Size:", m.group("SIZE")))

    if not disks:
        print("No disk information discovered.")
        return 10

    return 0


if __name__ == "__main__":
    sys.exit(main())
