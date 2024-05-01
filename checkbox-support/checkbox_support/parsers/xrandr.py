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
This module offers a parser that takes the output of xrandr and parses it
into a dictionary, where the keys are the output names and the values are
lists of modes, where each mode is a named tuple containing the resolution,
refresh rate, and whether the mode is preferred mode, and/or current mode.

Considerations:
The typical line from xrandr output looks like this:
  3840x2160  144.00 +  120.00*  99.95   60.00

If a mode is preferred, the `+` is appended to the refresh rate, like so:
    3840x2160  144.00+  120.00*  99.95   60.00

If a mode is the currently used mode, the `*` is appended, like so:
    3840x2160  144.00   120.00*  99.95   60.00

Given mode might be both, preferred and current, like so:
    1920x1080  144.00+  120.00*  99.95   60.00

The name of the output begins in the column 0, the next lines that inform
about the modes are indented, like so:
DP-3 AOC 2770M GDBFBHA000236
    1920x1080  60.00*  59.94   59.93   50.00
"""


import re
from collections import namedtuple, defaultdict

# Define the namedtuple for mode information
Mode = namedtuple(
    "Mode", ["resolution", "refresh_rate", "is_preferred", "is_current"]
)


def parse_xrandr_line(line):
    # Checking if it's a display information line
    if "connected" in line:
        # return the output name (e.g., eDP-1)
        return "output", line.split()[0]
    elif line.strip() and line[0] == " ":
        # It's a mode line
        mode_data = line.strip()
        parts = mode_data.split()
        resolution = parts[0]
        # handle multiple refresh rates on the same line
        refresh_rates = parts[1:]

        modes = []
        for rate in refresh_rates:
            try:
                refresh_rate = float(re.sub(r"[+*]", "", rate))
            except ValueError:
                # float couldn't be parsed
                continue
            is_preferred = "+" in rate
            is_current = "*" in rate
            modes.append(
                Mode(resolution, refresh_rate, is_preferred, is_current)
            )
        return "mode", modes
    return None


def parse_xrandr_output(output):
    output_dict = defaultdict(list)
    current_output = None
    for line in output.split("\n"):
        result = parse_xrandr_line(line)
        if result:
            line_type, data = result
            if line_type == "output":
                current_output = data
            elif line_type == "mode":
                output_dict[current_output].extend(data)
    return dict(output_dict)
