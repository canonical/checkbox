# Copyright 2024 Canonical Ltd.
# Written by:
#   Paolo Gentili <paolo.gentili@canonical.com>
#   Zhongning Li <zhongning.li@canonical.com>
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
from collections import OrderedDict
from enum import IntEnum
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


class Transform(IntEnum):
    NORMAL_0 = 0  # landscape
    NORMAL_90 = 1  # portrait right
    NORMAL_180 = 2  # landscape flipped
    NORMAL_270 = 3  # portrait left

    # The following are listed in the xml file
    # but they aren't available in gnome control center
    # maybe it's only intended for devices with an accelerometer?
    FLIPPED_0 = 4
    FLIPPED_90 = 5
    FLIPPED_180 = 6
    FLIPPED_270 = 7


# A plain 4-tuple with some basic info about the monitor
MonitorInfo = NamedTuple(
    "MonitorInfo",
    [
        ("connector", str),  # HDMI-1, eDP-1, ...
        ("vendor", str),  # vendor string like BOE, Asus, etc.
        ("product", str),
        ("serial", str),
    ],
)


# py3.5 can't use inline type annotations,
# otherwise the _*T types should be merged with their non-underscore versions
_MutterDisplayModeT = NamedTuple(
    "_MutterDisplayModeT",
    [
        ("id", str),
        ("width", int),
        ("height", int),
        ("refresh_rate", float),
        ("preferred_scale", float),
        ("supported_scales", List[float]),
        ("properties", Mapping[str, Any]),
    ],
)


class MutterDisplayMode(_MutterDisplayModeT):
    @property
    def is_current(self) -> bool:
        return self.properties.get("is-current", False)

    @property
    def is_preferred(self) -> bool:
        return self.properties.get("is-preferred", False)

    @property
    def resolution(self) -> str:
        """
        Resolution string, makes this class compatible with the Mode type
        !! WARNING: This property does not exist on the original dbus object
        !! This is only here for code that expects a string, new code should
        !! use the width and height numbers
        """
        return "{}x{}".format(self.width, self.height)


_PhysicalMonitorT = NamedTuple(
    "_PhysicalMonitorT",
    [
        ("info", MonitorInfo),
        ("modes", List[MutterDisplayMode]),
        # See: https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/
        # dbus-interfaces/org.gnome.Mutter.DisplayConfig.xml#L414
        ("properties", Mapping[str, Any]),
    ],
)


class PhysicalMonitor(_PhysicalMonitorT):

    @classmethod
    def from_variant(cls, v: GLib.Variant):
        # not going to do extensive checks here
        # since get_current_state already checked
        assert len(v) == 3
        return cls(
            MonitorInfo(*v[0]), [MutterDisplayMode(*raw) for raw in v[1]], v[2]
        )

    @property
    def is_builtin(self) -> bool:
        return self.properties.get("is-builtin", False)


_LogicalMonitorT = NamedTuple(
    "_LogicalMonitorT",
    [
        ("x", int),
        ("y", int),
        ("scale", float),
        ("transform", Transform),
        ("is_primary", bool),
        ("monitors", List[MonitorInfo]),
        ("properties", Mapping[str, Any]),
    ],
)


class LogicalMonitor(_LogicalMonitorT):
    @classmethod
    def from_variant(cls, v: GLib.Variant):
        assert len(v) == 7
        return cls(
            *v[0:5],  # the first 5 elements are flat, so just spread them
            [MonitorInfo(*m) for m in v[5]],  # type: ignore
            v[6],  # type: ignore
        )


_MutterDisplayConfigT = NamedTuple(
    "_MutterDisplayConfigT",
    [
        ("serial", int),
        ("physical_monitors", List[PhysicalMonitor]),
        ("logical_monitors", List[LogicalMonitor]),
        # technically value type is GLib.Variant
        ("properties", Mapping[str, Any]),
    ],
)


class MutterDisplayConfig(_MutterDisplayConfigT):
    """The top level object that represents
    the return value of the GetCurrentState dbus call
    """

    @classmethod
    def from_variant(cls, v: GLib.Variant):
        return cls(
            v[0],
            [PhysicalMonitor.from_variant(physical) for physical in v[1]],
            [LogicalMonitor.from_variant(logical) for logical in v[2]],
            v[3],
        )

    @property
    def supports_mirroring(self) -> bool:
        return self.properties.get("supports-mirroring", False)

    @property
    def layout_mode(self) -> Optional[int]:
        # only 2 possible layouts
        # layout-mode = 2 => physical, 1 => logical
        # If the key doesn't exist, then layout mode can't be changed
        return self.properties.get("layout-mode", None)

    @property
    def supports_changing_layout_mode(self) -> bool:
        return self.properties.get("supports-changing-layout-mode", False)

    @property
    def global_scale_required(self) -> bool:
        return self.properties.get("global-scale-required", False)


ResolutionFilter = Callable[[List[MutterDisplayMode]], List[MutterDisplayMode]]
# this only appears in apply_monitors_config
# it's very similar to LogicalMonitor but the last list element is different
LogicalMonitorConfig = Tuple[
    int,  # x offset
    int,  # y offset
    float,  # scale, 1.0 for 100%
    Transform,  # transformation
    bool,  # is primary
    List[
        Tuple[
            str,  # connector id, same as <MutterDisplayMode>.connector
            str,  # monitor mode id, same as <PhysicalMonitor>.id
            Dict[
                # only 2 possible keys:
                # underscanning: bool
                # color-mode: uint32
                str,
                "bool|int",
            ],
        ]
    ],
]


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
    CONFIG_VARIANT_TYPE = GLib.VariantType.new(
        "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})"
    )

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
        """
        Get the connector names of each connected monitor, even if inactive.
        """
        state = self.get_current_state()
        return {monitor.info.connector for monitor in state.physical_monitors}

    def get_current_resolutions(self) -> Dict[str, str]:
        """
        Get current active resolutions for each monitor.
        - Key is connector name like "eDP-1", value is resolution string
        - This method is only here to implement the one from the
          parent abstract class, new code should directly access the resolution
          integers from get_current_state
        """

        state = self.get_current_state()
        resolution_map = {}  # type: dict[str, str]

        for monitor in state.physical_monitors:
            for mode in monitor.modes:
                if mode.is_current:
                    resolution_map[monitor.info.connector] = mode.resolution
        return resolution_map

    def set_extended_mode(self) -> Dict[str, str]:
        """
        Set to extend mode so that each monitor can be displayed
        at preferred, or if missing, maximum resolution.
        - This always arranges the displays in a line

        :return configuration: ordered dict of applied Configuration
        """
        state = self.get_current_state()

        extended_logical_monitors = []  # type: list[LogicalMonitorConfig]
        # key is connector name, value is resolution string
        configuration = OrderedDict()  # type: OrderedDict[str, str]

        # the x offset of the current monitor
        # this will accumulate the width of each monitor as the iteration runs
        # so that all monitors are arranged in a straight line
        position_x = 0
        for physical_monitor in state.physical_monitors:
            try:
                target_mode = next(
                    mode
                    for mode in physical_monitor.modes
                    if mode.is_preferred
                )
            except StopIteration:
                target_mode = self._get_mode_at_max(physical_monitor.modes)

            if type(target_mode) is not MutterDisplayMode:
                # _get_mode_at_max should only be a filter
                # and not change any of the items
                raise TypeError("Unexpected mode:", target_mode)

            extended_logical_monitors.append(
                (
                    position_x,  # x
                    0,  # y
                    1.0,  # scale
                    Transform.NORMAL_0,
                    position_x == 0,  # first monitor is primary
                    # .id is specific to MutterDisplayMode
                    [(physical_monitor.info.connector, target_mode.id, {})],
                )
            )
            position_x += int(target_mode.width)
            configuration[physical_monitor.info.connector] = (
                target_mode.resolution
            )

        self._apply_monitors_config(state.serial, extended_logical_monitors)
        return configuration

    def cycle(
        self,
        resolution: bool = True,
        transform: bool = False,
        resolution_filter: Optional[ResolutionFilter] = None,
        post_cycle_action: Optional[Callable[..., Any]] = None,
        **post_cycle_action_kwargs
    ):
        """
        Automatically cycle through the supported monitor configurations.

        Args:
            resolution: Cycling the resolution or not.

            transform: Cycling the transform or not.

            resolution_filter: For filtering resolution then returning needed,
                    it will take List[Mode] as parameter and return
                    the same data type

            post_cycle_action: Called after each cycle for each monitor,
                    the string is constructed by
                    [monitor name]_[resolution]_[transform]_.
                    Please note that the delay is needed inside this
                    callback to wait the monitors to response

            kwargs: args for post_cycle_action
        """
        connectors = []  # type: list[str]
        modes_list = []  # type: list[list[MutterDisplayMode]]
        transform_list = (
            (
                Transform.NORMAL_0,
                Transform.NORMAL_90,
                # preserving original behavior in case something depends on it
                Transform.FLIPPED_180,
                Transform.NORMAL_270,
            )
            if transform
            else (Transform.NORMAL_0,)
        )
        transformation_name_map = {
            Transform.NORMAL_0: "normal",
            Transform.NORMAL_270: "left",
            Transform.FLIPPED_180: "inverted",
            Transform.NORMAL_90: "right",
        }

        # for multiple monitors, we need to create resolution combination
        # modes_list[N] is a list of modes of monitor N
        state = self.get_current_state()
        for monitor in state.physical_monitors:
            connectors.append(monitor.info.connector)
            if resolution_filter is not None:
                modes_list.append(resolution_filter(monitor.modes))
            else:
                modes_list.append(monitor.modes)

        for combined_mode in itertools.product(*modes_list):
            for trans in transform_list:
                logical_monitors = []  # type: list[LogicalMonitorConfig]
                position_x = 0
                unique_str = ""  # unique string for the current monitor state
                for connector, mode in zip(connectors, combined_mode):
                    transformation_str = transformation_name_map[trans]
                    unique_str += "{}_{}_{}_".format(
                        connector, mode.resolution, transformation_str
                    )
                    logical_monitors.append(
                        (
                            position_x,  # x
                            0,  # y
                            1.0,  # scale
                            trans,  # rotation
                            position_x == 0,  # make the first monitor primary
                            # specify target connector name and mode
                            [(connector, mode.id, {})],
                        )
                    )

                    print(
                        "Setting",
                        connector,
                        "to mode:",
                        mode.id,
                        "transform:",
                        transformation_str,
                        flush=True,
                    )  # checkbox runtime might buffer this,
                    # force a flush here so it doesn't look frozen

                    x_offset = (
                        mode.height
                        if trans in (Transform.NORMAL_90, Transform.NORMAL_270)
                        else mode.width
                    )  # left and right should convert x and y
                    position_x += x_offset
                # Sometimes the NVIDIA driver won't update the state.
                # Get the state before applying to avoid this issue.
                state = self.get_current_state()
                self._apply_monitors_config(state.serial, logical_monitors)

                if post_cycle_action is not None:
                    post_cycle_action(unique_str, **post_cycle_action_kwargs)

                print("-" * 80, flush=True)  # just a divider

            if not resolution:
                break
        # change back to preferred monitor configuration
        self.set_extended_mode()

    def get_current_state(self) -> MutterDisplayConfig:
        """
        Use the DBus signal 'GetCurrentState' to get the available monitors
        and related modes.
        The return type wraps the dbus object specified here:
        https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/dbus-interfaces/
        org.gnome.Mutter.DisplayConfig.xml

        This is the entry point for getting any kind of monitor info
        """

        raw = self._proxy.call_sync(
            method_name="GetCurrentState",
            parameters=None,  # doesn't take any args
            # don't auto start dbus "recipient"'s process if it's not running
            # so if gnome is somehow dead, don't automatically fix it
            flags=Gio.DBusCallFlags.NO_AUTO_START,
            timeout_msec=-1,  # don't timeout
            cancellable=None,
        )

        if not raw.get_type().equal(self.CONFIG_VARIANT_TYPE):
            raise TypeError(
                "DBus GetCurrentState returned unexpected type: "
                + str(raw.get_type())
            )

        return MutterDisplayConfig.from_variant(raw)

    def _apply_monitors_config(
        self, serial: int, logical_monitors: List[LogicalMonitorConfig]
    ):
        """Call the DBus signal 'ApplyMonitorsConfig' to apply the config in
        logical_monitors

        Original specification:
        https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/dbus-interfaces/
        org.gnome.Mutter.DisplayConfig.xml#L477

        :param serial: The <MutterDisplayConfig>.serial integer
            from get_current_state
        :param logical_monitors: The actual logical monitor configuration
            - Use the LogicalMonitorConfig type to check if the config object
              has the correct shape
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
