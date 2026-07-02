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
import os
import sys
from pathlib import Path
from checkbox_support.dbus.gnome_monitor import MonitorConfigGnome


class SysfsDrmCardInfo:
    def __init__(self, path: Path) -> None:
        if not path.is_dir():
            raise ValueError(
                "{} requires a directory path.".format(type(self).__name__)
                + "Example: /sys/class/drm/card1-eDP-1/"
            )
        with open(Path(path) / "modes") as f:
            # Topmost line in the modes file is the max resolution
            max_resolution = f.readline().strip()
            if not max_resolution:
                raise ValueError(
                    "No monitor is connected to this port {}".format(path)
                )
            str_width, str_height = max_resolution.split("x")
            self.max_width, self.max_height = int(str_width), int(str_height)

        self.enabled = (
            Path(path) / "enabled"
        ).read_text().strip() == "enabled"
        self.is_connected = (
            Path(path) / "status"
        ).read_text().strip() == "connected"
        self.port = os.path.basename(path)
        self.dpms_enabled = (Path(path) / "dpms").read_text().strip() == "On"

    def __str__(self) -> str:
        return "{}: {}x{} enabled={}, is_connected={}, dpms_enabled={}".format(
            self.port,
            self.max_width,
            self.max_height,
            self.enabled,
            self.is_connected,
            self.dpms_enabled,
        )


def get_sysfs_info():
    """
    Go through each graphics cards sysfs entries to find max resolution if
    connected to a monitor.
    Return a list of ports with information about them.
    """
    out = []  # type: list[SysfsDrmCardInfo]
    for str_path in glob("/sys/class/drm/card*-*"):
        try:
            out.append(SysfsDrmCardInfo(Path(str_path)))
        except ValueError:
            continue
    return out


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
    for drm_card in sysfs_info:
        print(" -", drm_card)
        if drm_card.enabled:
            total_sysfs_res += drm_card.max_width * drm_card.max_height

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
