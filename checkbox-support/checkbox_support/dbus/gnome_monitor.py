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

import itertools
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
)

from checkbox_support.monitor_config import MonitorConfig
from gi.repository import Gio, GLib  # type: ignore


class Mode(NamedTuple):
    id: str
    resolution: str
    is_preferred: bool
    is_current: bool


class Transform:
    NORMAL_0 = 0
    NORMAL_90 = 1
    NORMAL_180 = 2
    NORMAL_270 = 3
    FLIPPED_0 = 4
    FLIPPED_90 = 5
    FLIPPED_180 = 6
    FLIPPED_270 = 7


class MutterDisplayMode(NamedTuple):
    id: str
    width: int
    height: int
    refresh_rate: float
    preferred_scale: float
    supported_scales: List[float]
    # usually has the 'is-current' and 'is-preferred' keys
    properties: Mapping[str, Any]


class MonitorInfo(NamedTuple):
    connector: str  # HDMI-1, eDP-1, ...
    vendor: str  # vendor string like BOE
    product: str
    serial: str


class PhysicalMonitor(NamedTuple):
    info: MonitorInfo
    modes: List[MutterDisplayMode]
    # optional props may include
    # "width-mm": int, "height-mm": int, "is-underscanning": bool,
    # "max-screen-size": str,
    # "is-builtin", "display-name"
    properties: Mapping[str, Any]

    @classmethod
    def from_tuple(cls, t: Tuple):
        assert len(t) == 3
        return cls(
            MonitorInfo(*t[0]), [MutterDisplayMode(*raw) for raw in t[1]], t[2]
        )


class LogicalMonitor(NamedTuple):
    x: int
    y: int
    scale: float
    transform: Transform  # u32 enum
    is_primary: bool
    # list of physical monitors that formed this logical monitor
    monitors: List[MonitorInfo]
    properties: Mapping[str, Any]

    @classmethod
    def from_tuple(cls, t: Tuple):
        assert len(t) == 7
        return cls(
            *t[0:5], # first 5 elements are "flat"
            [MonitorInfo(*m) for m in t[5]],  # type: ignore
            t[6],  # type: ignore
        )


class MutterDisplayConfig(NamedTuple):
    serial: int
    physical_monitors: List[PhysicalMonitor]
    logical_monitors: List[LogicalMonitor]
    # optional properties, may contain
    # "supports-mirroring", "layout-mode", "supports-changing-layout-mode"
    # "global-scale-required"
    properties: Mapping[str, Any]

    @classmethod
    def from_tuple(cls, t: Tuple):
        assert len(t) == 4
        return cls(
            t[0],
            [PhysicalMonitor.from_tuple(physical) for physical in t[1]],
            [LogicalMonitor.from_tuple(logical) for logical in t[2]],
            t[3],
        )


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

    def get_connected_monitors(self) -> Set[str]:
        """Get list of connected monitors, even if inactive."""
        state = self._get_current_state()
        return {monitor for monitor in state[1]}

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
        at preferred, or if missing, maximum resolution.

        :return configuration: ordered list of applied Configuration
        """
        state = self._get_current_state()

        extended_logical_monitors = []
        configuration = {}

        position_x = 0
        for monitor, modes in state[1].items():
            try:
                target_mode = next(mode for mode in modes if mode.is_preferred)
            except StopIteration:
                target_mode = self._get_mode_at_max(modes)
            extended_logical_monitors.append(
                (
                    position_x,
                    0,
                    1.0,
                    0,
                    position_x == 0,  # first monitor is primary
                    [(monitor, target_mode.id, {})],
                )
            )
            position_x += int(target_mode.resolution.split("x")[0])
            configuration[monitor] = target_mode.resolution

        self._apply_monitors_config(state[0], extended_logical_monitors)
        return configuration

    def cycle(
        self,
        resolution: bool = True,
        transform: bool = False,
        resolution_filter: Optional[Callable[[List[Mode]], List[Mode]]] = None,
        action: Optional[Callable[..., Any]] = None,
        **kwargs
    ):
        """
        Automatically cycle through the supported monitor configurations.

        Args:
            resolution: Cycling the resolution or not.

            transform: Cycling the transform or not.

            resolution_filter: For filtering resolution then returning needed,
                    it will take List[Mode] as parameter and return
                    the same data type

            action: For extra steps for each cycle,
                    the string is constructed by
                    [monitor name]_[resolution]_[transform]_.
                    Please note that the delay is needed inside this
                    callback to wait the monitors to response
        """
        monitors = []
        modes_list = []
        # ["normal": 0, "left": 1, "inverted": 6, "right": 3]
        trans_list = [0, 1, 6, 3] if transform else [0]

        # for multiple monitors, we need to create resolution combination
        state = self._get_current_state()
        for monitor, modes in state[1].items():
            monitors.append(monitor)
            if resolution_filter:
                modes_list.append(resolution_filter(modes))
            else:
                modes_list.append(modes)
        mode_combination = list(itertools.product(*modes_list))

        for mode in mode_combination:
            for trans in trans_list:
                logical_monitors = []
                position_x = 0
                uni_string = ""
                for monitor, m in zip(monitors, mode):
                    uni_string += "{}_{}_{}_".format(
                        monitor,
                        m.resolution,
                        {
                            0: "normal",
                            1: "left",
                            3: "right",
                            6: "inverted",
                        }.get(trans),
                    )
                    logical_monitors.append(
                        (
                            position_x,
                            0,
                            1.0,
                            trans,
                            position_x == 0,  # first monitor is primary
                            [(monitor, m.id, {})],
                        )
                    )
                    # left and right should convert x and y
                    xy = 1 if (trans == 1 or trans == 3) else 0
                    position_x += int(m.resolution.split("x")[xy])
                # Sometimes the NVIDIA driver won't update the state.
                # Get the state before applying to avoid this issue.
                state = self._get_current_state()
                self._apply_monitors_config(state[0], logical_monitors)
                if action:
                    action(uni_string, **kwargs)
            if not resolution:
                break
        # change back to preferred monitor configuration
        self.set_extended_mode()

    def get_current_state_raw(self) -> MutterDisplayConfig:
        raw = self._proxy.call_sync(
            method_name="GetCurrentState",
            parameters=None,
            flags=Gio.DBusCallFlags.NO_AUTO_START,
            timeout_msec=-1,
            cancellable=None,
        ).unpack()
        assert type(raw) is tuple
        return MutterDisplayConfig.from_tuple(raw)

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
