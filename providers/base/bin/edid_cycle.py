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

from checkbox_support.dbus.gnome_monitor import (
    GnomeMonitorConfig,
)  # noqa: E402
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


def discover_video_output_device(
    zapper_host: str, gnome_monitor: GnomeMonitorConfig
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

    devices = gnome_monitor.get_current_resolutions().keys()

    # It doesn't really matter which EDID file we set in this function:
    # we just want to recognize the port type and index, not the resolution.
    _set_edid(zapper_host, EDID_FILES[0])

    # Wait until the list of active devices changes.
    # From manual testing, 5 seconds seem more than
    # enough for such changes to happen.
    targets = []
    for _ in range(5):
        targets = list(
            gnome_monitor.get_current_resolutions().keys() - devices
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
    gnome_monitor: GnomeMonitorConfig,
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
        _switch_edid(zapper_host, gnome_monitor, edid_file, video_device)
        gnome_monitor.set_extended_mode()
    except TimeoutError as exc:
        raise AssertionError("Timed out switching EDID") from exc

    actual_res = gnome_monitor.get_current_resolutions()[video_device]
    if actual_res != resolution:
        raise AssertionError(
            "FAIL, got {} but {} expected".format(actual_res, resolution)
        )

    print("PASS")


def _switch_edid(zapper_host, gnome_monitor, edid_file, video_device):
    """Clear EDID and then 'plug' back a new monitor."""

    _clear_edid(zapper_host)
    _wait_edid_change(gnome_monitor, video_device, False)

    _set_edid(zapper_host, edid_file)
    _wait_edid_change(gnome_monitor, video_device, True)


def _set_edid(zapper_host, edid_file):
    """Request EDID change to Zapper."""
    with open(str(edid_file), "rb") as f:
        zapper_run(zapper_host, "change_edid", f.read())


def _clear_edid(zapper_host):
    """Request EDID clear to Zapper."""
    zapper_run(zapper_host, "change_edid", None)


def _check_connected(gnome_monitor, device):
    """Check if the video input device is recognized and active."""

    return device in gnome_monitor.get_current_resolutions().keys()


def _wait_edid_change(gnome_monitor, video_device, expected):
    """
    Wait until `expected` connection state is reached.
    Times out after 5 seconds.
    """
    iteration = 0
    max_iter = 5
    sleep = 1
    while (
        _check_connected(gnome_monitor, video_device) != expected
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
    gnome_monitor = GnomeMonitorConfig()

    try:
        video_device = discover_video_output_device(args.host, gnome_monitor)
        print("Testing EDID cycling on {}".format(video_device))
    except IOError as exc:
        raise SystemExit(
            "Cannot detect the target video output device."
        ) from exc

    failed = False

    with zapper_monitor(args.host):
        for edid_file in EDID_FILES:
            try:
                test_edid(args.host, gnome_monitor, edid_file, video_device)
            except AssertionError as exc:
                print(exc.args[0])
                failed = True

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
