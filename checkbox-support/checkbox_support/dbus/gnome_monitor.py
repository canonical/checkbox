# Copyright 2024 Canonical Ltd.
# Written by:
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
a new logical monitor configuration via DBus and Mutter.

Original script that inspired this class:
- https://gitlab.gnome.org/GNOME/mutter/-/blob/main/tools/get-state.py
"""

from collections import namedtuple
from typing import Dict, List, Tuple
from gi.repository import GLib, Gio

from checkbox_support.monitor_config import MonitorConfig

Mode = namedtuple("Mode", ["id", "resolution", "is_preferred", "is_current"])


class MonitorConfigGnome(MonitorConfig):
    """Get and modify the current Monitor configuration via DBus."""

    NAME = "org.gnome.Mutter.DisplayConfig"
    INTERFACE = "org.gnome.Mutter.DisplayConfig"
    OBJECT_PATH = "/org/gnome/Mutter/DisplayConfig"

    def __init__(self):
        self._proxy = Gio.DBusProxy.new_for_bus_sync(
            bus_type=Gio.BusType.SESSION,
            flags=Gio.DBusProxyFlags.NONE,
            info=None,
            name=self.NAME,
            object_path=self.OBJECT_PATH,
            interface_name=self.INTERFACE,
            cancellable=None,
        )

    def get_current_resolutions(self) -> Dict[str, str]:
        """Get current active resolutions for each monitor."""

        state = self._get_current_state()
        return {
            monitor: mode.resolution
            for monitor, modes in state[1].items()
            for mode in modes
            if mode.is_current
        }

    def set_extended_mode(self):
        """
        Set to extend mode so that each monitor can be displayed
        at preferred resolution.
        """
        state = self._get_current_state()

        extended_logical_monitors = []

        position_x = 0
        for monitor, modes in state[1].items():
            preferred = next(mode for mode in modes if mode.is_preferred)
            extended_logical_monitors.append(
                (
                    position_x,
                    0,
                    1.0,
                    0,
                    position_x == 0,  # first monitor is primary
                    [(preferred.id, monitor, {})],
                )
            )
            position_x += int(preferred.resolution.split("x")[0])

        self._apply_monitors_config(state[0], extended_logical_monitors)

    def _get_current_state(self) -> Tuple[str, Dict[str, List[Mode]]]:
        """
        Run the GetCurrentState DBus request and assert the return
        format is correct.
        """
        state = self._proxy.call_sync(
            method_name="GetCurrentState",
            parameters=None,
            flags=Gio.DBusCallFlags.NO_AUTO_START,
            timeout_msec=-1,
            cancellable=None,
        )

        return (
            state[0],
            {
                monitor[0][0]: [
                    Mode(
                        mode[0],
                        "{}x{}".format(mode[1], mode[2]),
                        mode[6].get("is-preferred", False),
                        mode[6].get("is-current", False),
                    )
                ]
                for monitor in state[1]
                for mode in monitor[1]
            },
        )

    def _get_max_resolution(
        self, state: GLib.Variant
    ) -> Dict[str, Tuple[str, int, int]]:
        """Get the maximum resolution from the available modes."""

        def get_max(modes):
            max_resolution = (0, 0)
            max_resolution_mode = ""
            for mode in modes:
                resolution = (mode[1], mode[2])
                if resolution > max_resolution:
                    max_resolution = resolution
                    max_resolution_mode = mode[0]
            return max_resolution_mode, max_resolution[0], max_resolution[1]

        return {monitor[0][0]: get_max(monitor[1]) for monitor in state[1]}

    def _apply_monitors_config(self, serial: str, logical_monitors: List):
        """Apply the given monitor configuration."""
        self._proxy.call_sync(
            method_name="ApplyMonitorsConfig",
            parameters=GLib.Variant(
                "(uua(iiduba(ssa{sv}))a{sv})",
                (
                    serial,
                    1,  # temporary setting
                    logical_monitors,
                    {},
                ),
            ),
            flags=Gio.DBusCallFlags.NONE,
            timeout_msec=-1,
            cancellable=None,
        )
