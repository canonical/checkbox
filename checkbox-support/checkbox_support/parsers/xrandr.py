# Copyright 2024 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Paolo Gentili <paolo.gentili@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
"""
This modules includes a utility to get display information and set
a new logical monitor configuration via xrandr.

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
import subprocess
from collections import defaultdict, namedtuple
from typing import Dict
from checkbox_support.monitor_config import MonitorConfig

Mode = namedtuple(
    "Mode", ["resolution", "refresh_rate", "is_preferred", "is_current"]
)


class MonitorConfigX11(MonitorConfig):
    """A generic monitor config for X11, based on xrandr."""

    def get_current_resolutions(self) -> Dict[str, str]:
        """Get current active resolutions for each monitor."""
        state = self._get_current_state()

        return {
            monitor: mode.resolution
            for monitor, modes in state.items()
            for mode in modes
            if mode.is_current
        }

    def set_extended_mode(self) -> Dict[str, str]:
        """
        Set to extend mode so that each monitor can be displayed
        at preferred, or if missing, maximum resolution.

        :return configuration: ordered list of applied Configuration
        """
        state = self._get_current_state()
        cmd = ["xrandr"]
        configuration = {}

        previous = None
        for monitor, modes in sorted(state.items()):
            try:
                target_mode = next(mode for mode in modes if mode.is_preferred)
            except StopIteration:
                target_mode = self._get_mode_at_max(modes)
            xrandr_args = "--output {} --mode {} {}".format(
                monitor,
                target_mode.resolution,
                (
                    "--right-of {}".format(previous)
                    if previous
                    else "--primary --pos 0x0"
                ),
            )
            previous = monitor
            cmd.extend(xrandr_args.split())
            configuration[monitor] = target_mode.resolution

        subprocess.run(cmd)
        return configuration

    def _parse_xrandr_line(self, line):
        """
        Parse an xrandr line which could specify a new
        monitor, or, the description of a new monitor mode.
        """

        if "connected" in line:  # it's a display info line
            return "output", line.split()[0]
        elif line.strip() and line[0] == " ":  # it's a mode line
            mode_data = line.strip()
            resolution = mode_data.split()[0]

            # handle multiple refresh rates on the same line
            refresh_rates = re.findall(r"[0-9]+\.[0-9]+ ?[*+]*", mode_data)

            modes = []
            for rate in refresh_rates:
                refresh_rate = float(re.sub(r"[+*]", "", rate))

                is_preferred = "+" in rate
                is_current = "*" in rate
                modes.append(
                    Mode(resolution, refresh_rate, is_preferred, is_current)
                )
            return "mode", modes

        return None

    def _get_current_state(self):
        """
        Parse the xrandr output and return the current state
        of the display configuration.
        """
        output_dict = defaultdict(list)

        output = subprocess.check_output(
            ["xrandr"],
            universal_newlines=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        )

        current_output = None
        for line in output.split("\n"):
            result = self._parse_xrandr_line(line)
            if result:
                line_type, data = result
                if line_type == "output":
                    current_output = data
                elif line_type == "mode":
                    output_dict[current_output].extend(data)

        return dict(output_dict)
