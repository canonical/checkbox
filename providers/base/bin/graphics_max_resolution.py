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

from glob import glob
import sys
from pathlib import Path
from checkbox_support.dbus.gnome_monitor import MonitorConfigGnome


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


def main():
    mutter_state = MonitorConfigGnome().get_current_state()

    failed = False
    total_gnome_res = 0
    for monitor in mutter_state.physical_monitors:
        curr = monitor.get_current_mode()
        msg_prefix = "Monitor '{} {}', connected at '{}'".format(
            monitor.info.vendor, monitor.info.product, monitor.info.connector
        )

        # preserve the original logic of ignoring inactive monitors
        if curr is None:
            print("[ WARN ]", msg_prefix, "has no active mode. Skipping.")
            continue

        max_w, max_h = monitor.get_max_resolution()
        if curr.width != max_w or curr.height != max_h:
            print(
                "[ ERR ]",
                msg_prefix,
                "is not using its maximum resolution.",
                "Expected {}x{}, but got {}x{}".format(
                    max_w, max_h, curr.width, curr.height
                ),
                file=sys.stderr,
            )
            failed = True
        else:
            print(
                "[ OK ] {} is set to its maximum resolution".format(
                    msg_prefix
                ),
                "{}x{}".format(curr.width, curr.height),
            )
            total_gnome_res += curr.width * curr.height

    if failed:
        # no need to do the sysfs check if gnome
        # is already NOT using the max resolution
        raise SystemExit("See the logs above to see which monitors failed")

    # now we know gnome is using the maximum resolution
    # compare it with sysfs
    total_sysfs_res = 0
    print("Checking against these max resolutions shown in sysfs:")
    sysfs_info = get_sysfs_info()
    for p in sysfs_info:
        print(
            " - {}: {}x{} ({})".format(
                p["port"], p["width"], p["height"], p["enabled"]
            )
        )
        if p["enabled"] == "enabled":
            total_sysfs_res += int(p["width"]) * int(p["height"])

    # instead of checking each individual display
    # where we have to do edid matching
    # just add them all together and compare the sum
    if total_gnome_res == total_sysfs_res:
        print("[ OK ] Maximum resolution reported by GNOME matches sysfs")
    else:
        raise SystemExit(
            "[ ERR ] Maximum resolution reported by GNOME does not match sysfs"
        )


if __name__ == "__main__":
    main()
