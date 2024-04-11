#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# color_depth_info.py
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
#
# Authors: Alberto Milone <alberto.milone@canonical.com>
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
    The get_color_depth got information from Xorg.*.log
"""

import os
import re
import sys

from glob import glob


def get_color_depth(log_dir="/var/log/"):
    """Return color depth and pixmap format"""

    # find the most recent X.org log
    depth = 8
    pixmap_format = 8
    log = None
    max_time = 0
    for log in glob(os.path.join(log_dir, "Xorg.*.log")):
        mtime = os.stat(log).st_mtime
        if mtime > max_time:
            max_time = mtime
            current_log = log
    if current_log is None:
        depth = 0
        pixmap_format = 0
        return (depth, pixmap_format)

    with open(current_log, "rb") as stream:
        for match in re.finditer(
            r"Depth (\d+) pixmap format is (\d+) bpp", str(stream.read())
        ):
            depth = int(match.group(1))
            pixmap_format = int(match.group(2))

    return (depth, pixmap_format)


def main():
    """main function"""

    depth, pixmap_format = get_color_depth()
    print(
        "Color Depth: {0}\nPixmap Format: {1} bpp".format(depth, pixmap_format)
    )
    if depth == 8:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
