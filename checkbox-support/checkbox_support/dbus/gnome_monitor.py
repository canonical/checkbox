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
    """
    Get and modify the current Monitor configuration via DBus.

    DBus interface doc at:
    https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/dbus-interfaces/
        org.gnome.Mutter.DisplayConfig.xml
    """

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

    def set_extended_mode(self) -> Dict[str, str]:
        """
        Set to extend mode so that each monitor can be displayed
        at maximum resolution.

        :return configuration: ordered list of applied Configuration
        """
        state = self._get_current_state()

        extended_logical_monitors = []
        configuration = {}

        position_x = 0
        for monitor, modes in state[1].items():
            max_mode = self._get_mode_at_max(modes)
            extended_logical_monitors.append(
                (
                    position_x,
                    0,
                    1.0,
                    0,
                    position_x == 0,  # first monitor is primary
                    [(monitor, max_mode.id, {})],
                )
            )
            position_x += int(max_mode.resolution.split("x")[0])
            configuration[monitor] = max_mode.resolution

        self._apply_monitors_config(state[0], extended_logical_monitors)
        return configuration

    def _get_current_state(self) -> Tuple[str, Dict[str, List[Mode]]]:
        """
        Using DBus signal 'GetCurrentState' to get the available monitors
        and related modes.

        Check the related DBus XML definition for details over the expected
        output data format.
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
                    for mode in monitor[1]
                ]
                for monitor in state[1]
            },
        )

    def _apply_monitors_config(self, serial: str, logical_monitors: List):
        """
        Using DBus signal 'ApplyMonitorsConfig' to apply the given monitor
        configuration.

        Check the related DBus XML definition for details over the expected
        input data format.
        """
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
