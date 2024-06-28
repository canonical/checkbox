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
from checkbox_support.monitor_config import MonitorConfig
from checkbox_support.dbus.gnome_monitor import MonitorConfigGnome
from checkbox_support.parsers.xrandr import MonitorConfigX11


def get_monitor_config() -> MonitorConfig:
    """
    Depending on the current host, initiate and return
    an appropriate MonitorConfig.
    """
    if "GNOME" in os.getenv("XDG_CURRENT_DESKTOP", ""):
        return MonitorConfigGnome()
    elif "x11" == os.getenv("XDG_SESSION_TYPE", ""):
        return MonitorConfigX11()

    raise ValueError("Can't find a proper MonitorConfig.")
