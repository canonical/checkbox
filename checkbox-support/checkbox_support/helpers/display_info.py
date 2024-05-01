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
This module provides a display system agnostic way to get information about
the available displays connected to the system.
"""

import os

import subprocess

from checkbox_support.parsers.xrandr import parse_xrandr_output, Mode
from checkbox_support.parsers.gnome_randr import parse_gnome_randr_output


def get_display_modes() -> "dict[str, Mode]":
    """
    Get the display modes for the connected displays.

    Returns:
        A dictionary where the keys are the output names and the values are
        lists of modes, where each mode is a named tuple containing the
        resolution, refresh rate, and whether the mode is preferred mode,
        and/or current mode.
    """

    if os.getenv("XDG_SESSION_TYPE") == "wayland":
        return parse_gnome_randr_output(
            subprocess.check_output(["gnome-randr"])
        )
    else:
        return parse_xrandr_output(subprocess.check_output(["xrandr"]))
