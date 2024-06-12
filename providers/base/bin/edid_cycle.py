#!/usr/bin/env python3
"""
This program tests whether the system changes the resolution automatically
when supplied with a new EDID information.

To run the test you need Zapper board connected and set up.
"""

import argparse
import pathlib
import os
import time
from contextlib import contextmanager
from typing import Dict, List, Tuple
from gi.repository import GLib, Gio

from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402

EDID_FILES = list(
    pathlib.Path(os.getenv("PLAINBOX_PROVIDER_DATA", ".")).glob("edids/*.edid")
)


@contextmanager
def zapper_monitor(zapper_host: str):
    """Unplug the Zapper monitor at the end of the test."""
    try:
        yield
    finally:
        _clear_edid(zapper_host)


class MonitorConfigDBus:
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

        config_variant_type = GLib.VariantType.new(
            "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})"
        )

        assert variant.get_type().equal(config_variant_type)
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


def discover_video_output_device(
    zapper_host: str, monitor_config: MonitorConfigDBus
) -> str:
    """
    Try to discover the output device connected to Zapper
    checking the difference in randr when a monitor gets
    plugged in.

    :param zapper_host: Target Zapper IP
    :return: Video Output Port, i.e. `HDMI-1`
    :raises IOError: cannot discover the video port under test
    """

    _clear_edid(zapper_host)

    # Not knowing the target I can't use a busy loop here
    # and I'm waiting for the DUT to react to the EDID change.
    time.sleep(5)

    devices = monitor_config.get_current_resolutions().keys()

    # It doesn't really matter which EDID file we set in this function:
    # we just want to recognize the port type and index, not the resolution.
    _set_edid(zapper_host, EDID_FILES[0])

    # Wait until the list of active devices changes.
    # From manual testing, 5 seconds seem more than
    # enough for such changes to happen.
    targets = []
    for _ in range(5):
        targets = list(
            monitor_config.get_current_resolutions().keys() - devices
        )
        if targets:
            break

        time.sleep(1)

    if len(targets) != 1:
        raise IOError(
            "Can't identify the video port under test, "
            "got {} new devices.".format(len(targets))
        )

    return targets[0]


def test_edid(
    zapper_host: str,
    monitor_config: MonitorConfigDBus,
    edid_file: pathlib.Path,
    video_device: str,
):
    """
    Set a EDID file and check whether the resolution
    is recognized and selected on DUT.

    :param zapper_host: Target Zapper IP
    :param edid_file: path to the EDID file to test
    :param video_device: video output port under test

    :raises AssertionError: in case of mismatch between set
                            and read resolution
    """
    resolution = edid_file.stem
    print("switching EDID to {}".format(resolution))

    try:
        _switch_edid(zapper_host, monitor_config, edid_file, video_device)
        monitor_config.set_extended_mode()
    except TimeoutError as exc:
        raise AssertionError("Timed out switching EDID") from exc

    actual_res = monitor_config.get_current_resolutions()[video_device]
    if actual_res != resolution:
        raise AssertionError(
            "FAIL, got {} but {} expected".format(actual_res, resolution)
        )

    print("PASS")


def _switch_edid(zapper_host, monitor_config, edid_file, video_device):
    """Clear EDID and then 'plug' back a new monitor."""

    _clear_edid(zapper_host)
    _wait_edid_change(monitor_config, video_device, False)

    _set_edid(zapper_host, edid_file)
    _wait_edid_change(monitor_config, video_device, True)


def _set_edid(zapper_host, edid_file):
    """Request EDID change to Zapper."""
    with open(str(edid_file), "rb") as f:
        zapper_run(zapper_host, "change_edid", f.read())


def _clear_edid(zapper_host):
    """Request EDID clear to Zapper."""
    zapper_run(zapper_host, "change_edid", None)


def _check_connected(monitor_config, device):
    """Check if the video input device is recognized and active."""

    return device in monitor_config.get_current_resolutions().keys()


def _wait_edid_change(monitor_config, video_device, expected):
    """
    Wait until `expected` connection state is reached.
    Times out after 5 seconds.
    """
    iteration = 0
    max_iter = 5
    sleep = 1
    while (
        _check_connected(monitor_config, video_device) != expected
        and iteration < max_iter
    ):
        time.sleep(sleep)
        iteration += 1

    if iteration == max_iter:
        raise TimeoutError(
            "Reacting to the EDID change took more than {}s.".format(
                max_iter * sleep
            )
        )


def main(args=None):
    """
    Test for different EDID files whether the resolution
    is recognized and selected on DUT.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Zapper IP address")
    args = parser.parse_args(args)
    monitor_config = MonitorConfigDBus()

    try:
        video_device = discover_video_output_device(args.host, monitor_config)
        print("Testing EDID cycling on {}".format(video_device))
    except IOError as exc:
        raise SystemExit(
            "Cannot detect the target video output device."
        ) from exc

    failed = False

    with zapper_monitor(args.host):
        for edid_file in EDID_FILES:
            try:
                test_edid(args.host, monitor_config, edid_file, video_device)
            except AssertionError as exc:
                print(exc.args[0])
                failed = True

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
