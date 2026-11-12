#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Zhongning Li <zhongning.li@canonical.com>
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


from checkbox_support.dbus.gnome_monitor import MonitorConfigGnome


def main():
    """
    Simply prints the resolution of each active monitor like this:

    eDP-1: 3072x1920
    HDMI-1: 1920x1080

    this is scaling-agnostic
    """
    resolutions = MonitorConfigGnome().get_current_resolutions()
    for connector, resolution in sorted(resolutions.items()):
        print(f"{connector}: {resolution}")


if __name__ == "__main__":
    main()
