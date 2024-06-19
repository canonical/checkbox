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

from typing import Dict, List, Tuple
from gi.repository import GLib, Gio


class GnomeMonitorConfig:
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
            monitor[0][0]: "{}x{}".format(mode[1], mode[2])
            for monitor in state[1]
            for mode in monitor[1]
            if mode[6].get("is-current")
        }

    def set_extended_mode(self):
        """
        Set to extend mode so that each monitor can be displayed
        at max resolution.
        """
        state = self._get_current_state()

        extended_logical_monitors = []
        position_x = 0

        for index, monitor in enumerate(state[1]):
            monitor_id = monitor[0][0]
            max_resolution = self._get_max_resolution(state)[monitor_id]
            extended_logical_monitors.append(
                (
                    position_x,
                    0,
                    1.0,
                    0,
                    index == 0,  # first monitor is primary
                    [(monitor_id, max_resolution[0], {})],
                )
            )
            position_x += max_resolution[1]

        self._apply_monitors_config(state[0], extended_logical_monitors)

    def _get_current_state(self) -> GLib.Variant:
        """
        Run the GetCurrentState DBus request and assert the return
        format is correct.
        """
        variant = self._proxy.call_sync(
            method_name="GetCurrentState",
            parameters=None,
            flags=Gio.DBusCallFlags.NO_AUTO_START,
            timeout_msec=-1,
            cancellable=None,
        )

        return variant

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
