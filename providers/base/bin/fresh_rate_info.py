#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# fresh_rate_info.py
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
#
# Authors: Shawn Wang <shawn.wang@canonical.com>
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
    The fresh_rate_info.py got information from xrandr
"""

import re
import sys
import subprocess


def xrandr_paser(data=None):
    """return an array(xrandrs)"""

    resolution = None
    xrandrs = list()
    for line in str(data).split("\n"):
        for match in re.finditer(r"(.+) connected (\d+x\d+)\+", line):
            connector = match.group(1)
            resolution = match.group(2)
            break
        if resolution is None:
            continue
        for match in re.finditer(r"{0}\s+(.+)\*".format(resolution), line):
            refresh_rate = match.group(1)
            xrandr = {
                "connector": connector,
                "resolution": resolution,
                "refresh_rate": refresh_rate,
            }
            xrandrs.append(xrandr)

    return xrandrs


def main():
    """main function"""

    try:
        data = subprocess.check_output(
            ["xrandr", "--current"], universal_newlines=True
        )
    except subprocess.CalledProcessError as exc:
        return exc.returncode

    xrandrs = xrandr_paser(data)
    for xrandr in xrandrs:
        output_str = "Connector({0}):\t Resolution: {1} \t RefreshRate: {2}"
        print(
            output_str.format(
                xrandr["connector"],
                xrandr["resolution"],
                xrandr["refresh_rate"],
            )
        )


if __name__ == "__main__":
    sys.exit(main())
