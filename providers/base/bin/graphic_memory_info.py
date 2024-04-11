#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# graphic_memory_info.py
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
    The graphic_memory_info.py got information from lspci
"""

import re
import sys
import subprocess

# 00:01.0 VGA compatible controller: \
# Advanced Micro Devices [AMD] nee ATI Wrestler [Radeon HD 6320] \
# (prog-if 00 [VGA controller])


def vgamem_paser(data=None):
    """Parsing type vga and find memory information"""

    device = None
    vgamems = list()
    for line in data.split("\n"):
        for match in re.finditer(r"(\d\d:\d\d\.\d) VGA(.+): (.+)", line):
            device = match.group(1)
            name = match.group(3)
        if device is None:
            continue
        # Memory at e0000000 (32-bit, prefetchable) [size=256M]
        for match in re.finditer(
            r"Memory(.+) prefetchable\) \[size=(\d+)M\]", line
        ):
            vgamem_size = match.group(2)
            vgamem = {
                "device": device,
                "name": name,
                "vgamem_size": vgamem_size,
            }
            vgamems.append(vgamem)
    return vgamems


def main():
    """main function
    lspci -v -s 00:01.0 | grep ' prefetchable'
    """

    try:
        data = subprocess.check_output(
            ["lspci", "-v"], universal_newlines=True
        )
    except subprocess.CalledProcessError as exc:
        return exc.returncode

    vgamems = vgamem_paser(data)
    for vgamem in vgamems:
        output_str = "Device({0})\t Name: {1}\tVGA Memory Size: {2}M"
        print(
            output_str.format(
                vgamem["device"], vgamem["name"], vgamem["vgamem_size"]
            )
        )


if __name__ == "__main__":
    sys.exit(main())
