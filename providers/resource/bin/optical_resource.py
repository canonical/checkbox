#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# color_depth_info
#
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
#
# Authors: Brendan Donegan <brendan.donegan@canonical.com>
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

"""
This script discovers the types of media supported by a named optical drive
and the capabilities available for that media. It uses the information
provided by udev for this purpose. Currently supported media types and
capabilities are:

* CD
  * Read
  * Write
  * Rewrite
* DVD
  * Read
  * Write
  * Rewrite
* Blu-Ray (BD)
  * Read
  * Write
  * Rewrite
"""

import sys

from argparse import ArgumentParser
from collections import OrderedDict
from subprocess import check_output, CalledProcessError

CAP_MAP = OrderedDict(
    [
        ("ID_CDROM_CD=1", "cd_read"),
        ("ID_CDROM_CD_R=1", "cd_write"),
        ("ID_CDROM_CD_RW=1", "cd_rewrite"),
        ("ID_CDROM_DVD=1", "dvd_read"),
        ("ID_CDROM_DVD_R=1", "dvd_write"),
        ("ID_CDROM_DVD_RW=1", "dvd_rewrite"),
        ("ID_CDROM_BD=1", "bd_read"),
        ("ID_CDROM_BD_R=1", "bd_write"),
        ("ID_CDROM_BD_RE=1", "bd_rewrite"),
    ]
)


def main():
    parser = ArgumentParser(
        "Shows which capabilities are supported "
        "by the specified optical device."
    )
    parser.add_argument(
        "device", help="The optical device to get capabilities for"
    )
    args = parser.parse_args()

    try:
        cdrom_id = check_output(
            ["/lib/udev/cdrom_id", args.device], universal_newlines=True
        ).split("\n")
    except CalledProcessError:
        return 1
    if cdrom_id:
        for cap in CAP_MAP:
            if cap in cdrom_id:
                print(CAP_MAP[cap] + ": supported")


if __name__ == "__main__":
    sys.exit(main())
