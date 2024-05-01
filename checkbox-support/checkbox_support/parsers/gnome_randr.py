# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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
This module takes the output of gnome-randr and parses it into a dictionary,
where the keys are the output names and the values are lists of modes, where
each mode is a named tuple containing the resolution, refresh rate, and
whether the mode is preffered mode, and/or current mode.

Considerations:
The typical line from gnome-randr output looks like this:
3840x2160@144.004  3840x2160       144.00          [x1.00]

If a mode is preferred, the `+` is appended to the refresh rate, like so:
              3840x2160@59.997  3840x2160       60.00+          [x1.00]

If a mode is the currently used mode, the `*` is appended, like so:
             3840x2160@120.000  3840x2160       120.00*         [x1.00]

Given mode might be both, preferred and current, like so:
              1920x1080@60.000  1920x1080       60.00*+         [x1.00+]


The name of the output begins in the column 0, the next lines that inform
about the modes are indented, like so:
DP-3 AOC 2770M GDBFBHA000236
              1920x1080@60.000  1920x1080       60.00*+         [x1.00+]
              1920x1080@59.940  1920x1080       59.94           [x1.00+]
              1920x1080@59.934  1920x1080       59.93           [x1.00+]
              1920x1080@50.000  1920x1080       50.00           [x1.00+]

"""

import re
import subprocess

from collections import namedtuple, defaultdict

from checkbox_support.parsers.xrandr import Mode


def parse_line(line):
    # Check if line is a mode line or output line
    if not line.startswith(" "):
        # It's an output line
        return "output", line.strip()
    else:
        # It's a mode line
        mode_data = line.strip()
        # Regex to extract the mode details
        pattern = (
            r"(\d+x\d+)@\d+\.\d+\s+(\d+x\d+)\s+(\d+\.\d+)(\*?\+?)\s+\[.*\]"
        )
        match = re.search(pattern, mode_data)
        if match:
            resolution = match.group(2)
            refresh_rate = float(match.group(3))
            flags = match.group(4)
            is_preferred = "+" in flags
            is_current = "*" in flags
            return "mode", Mode(
                resolution, refresh_rate, is_preferred, is_current
            )
    return "bad", None


def parse_gnome_randr_output(output):
    output_dict = defaultdict(list)
    current_output = None
    for line in output.split("\n"):
        line_type, data = parse_line(line)
        if line_type == "output":
            current_output = data
            if current_output:
                # there is an output, so let's force creating a new list
                output_dict[current_output] = []
        elif line_type == "mode":
            output_dict[current_output].append(data)
        elif line_type == "bad":
            # ignore bad lines
            pass

    return dict(output_dict)