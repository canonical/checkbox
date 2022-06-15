#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

import gi
from glob import glob
import os
import sys
from pathlib import Path

gi.require_versions({"Gtk": "3.0", "Gdk": "3.0"})
from gi.repository import Gdk, Gtk  # noqa: E402


def get_sysfs_info():
    """
    Go through each graphics cards sysfs entries to find max resolution if
    connected to a monitor.
    Return a list of ports with information about them.
    """
    ports = glob("/sys/class/drm/card*-*")
    entries = []
    for p in ports:
        with open(Path(p) / "modes") as f:
            # Topmost line in the modes file is the max resolution
            max_resolution = f.readline().strip()
        if max_resolution:
            # e.g. "/sys/class/drm/card0-HDMI-A-1"
            port = p.split("/")[-1]
            width, height = max_resolution.split("x")
            with open(Path(p) / "enabled") as f:
                enabled = f.readline().strip()
            with open(Path(p) / "dpms") as f:
                dpms = f.readline().strip()
            with open(Path(p) / "status") as f:
                status = f.readline().strip()
            port_info = {
                "port": port,
                "width": int(width),
                "height": int(height),
                "enabled": enabled,  # "enabled" or "disabled"
                "status": status,  # "connected" or "disconnected"
                "dpms": dpms,  # "On" or "Off"
            }
            entries.append(port_info)
    return entries


def get_monitors_info():
    """
    Get information (model, manufacturer, resolution) from each connected
    monitors using Gtk.
    Return a list of monitors with their information.
    """
    Gtk.init()
    display = Gdk.Display.get_default()
    monitors = []
    for i in range(display.get_n_monitors()):
        mon = display.get_monitor(i)
        monitor = {
            "model": mon.get_model(),
            "manufacturer": mon.get_manufacturer(),
            "width": mon.get_geometry().width,
            "height": mon.get_geometry().height,
            "scale_factor": mon.get_scale_factor(),
        }
        monitors.append(monitor)
    return monitors


if __name__ == "__main__":
    sysfs_entries = get_sysfs_info()
    mons_entries = get_monitors_info()
    total_sysfs_res = 0
    total_mons_res = 0
    compositor = os.environ.get("XDG_SESSION_TYPE")
    print("Current compositor: {}".format(compositor))
    print()
    print("Maximum resolution found for each connected monitors:")
    for p in sysfs_entries:
        port = p["port"]
        width = p["width"]
        height = p["height"]
        enabled = p["enabled"]
        status = p["status"]
        dpms = p["dpms"].lower()
        print(
            "\t{}: {}x{} ({}, {}, {})".format(
                port, width, height, dpms, status, enabled
            )
        )
        # If the monitor is disabled (e.g. "Single Display" mode), don't take
        # its surface into account.
        if enabled == "enabled":
            total_sysfs_res += width * height
    print()
    print("Current resolution found for each connected monitors:")
    for m in mons_entries:
        model = m["model"]
        manufacturer = m["manufacturer"]
        scale = m["scale_factor"]
        # Under X11, the returned width and height are in "application pixels",
        # not "device pixels", so it has to be multiplied by the scale factor.
        # However, Wayland always returns the "device pixels" width and height.
        #
        # Example: a 3840x2160 screen set to 200% scale will have
        # width = 1920, height = 1080, scale_factor = 2 on X11
        # width = 3840, height = 2160, scale_factor = 2 on Wayland
        if compositor == "x11":
            width = m["width"] * m["scale_factor"]
            height = m["height"] * m["scale_factor"]
        else:
            width = m["width"]
            height = m["height"]
        print(
            "\t{} ({}): {}x{} @{}%".format(
                model, manufacturer, width, height, scale * 100
            )
        )
        total_mons_res += width * height
    print()
    if total_sysfs_res == total_mons_res:
        print("The displays are configured at their maximum resolution.")
    else:
        sys.exit(
            (
                "The displays do not seem to be configured at their maximum "
                "resolution.\nPlease switch to the maximum resolution before "
                "continuing."
            )
        )
