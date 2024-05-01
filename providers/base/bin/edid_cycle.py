#!/usr/bin/env python3
"""
This program tests whether the system changes the resolution automatically
when supplied with a new EDID information.

To run the test you need Zapper board connected and set up.
"""
import argparse
import pathlib
import os
import re
import subprocess
import time

from checkbox_support.helpers.display_info import get_display_modes
from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402


EDID_FILES = list(
    pathlib.Path(os.getenv("PLAINBOX_PROVIDER_DATA", ".")).glob("edids/*.edid")
)

def get_active_devices():
    """
    Get the list of active video ouput devices.

    The pattern we're looking for is <port-type>-<port-index>
    for instance HDMI-1 or DP-5.
    """
    active = set()

    for output, modes in get_display_modes().items():
        if any(mode.is_current for mode in modes):
            active.add(output)
    return active

def discover_video_output_device(zapper_host):
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

    devices = get_active_devices()

    # It doesn't really matter which EDID file we set in this function:
    # we just want to recognize the port type and index, not the resolution.
    _set_edid(zapper_host, EDID_FILES[0])

    # Wait until the list of active devices changes.
    # From manual testing, 5 seconds seem more than
    # enough for such changes to happen.
    targets = []
    for _ in range(5):
        targets = list(get_active_devices() - devices)
        if targets:
            break

        time.sleep(1)

    if len(targets) != 1:
        raise IOError(
            "Can't identify the video port under test, "
            "got {} new devices.".format(len(targets))
        )

    return targets[0]


def test_edid(zapper_host, edid_file, video_device):
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
        _switch_edid(zapper_host, edid_file, video_device)
    except TimeoutError as exc:
        raise AssertionError("Timed out switching EDID") from exc

    actual_res = _check_resolution(video_device)
    if actual_res != resolution:
        raise AssertionError(
            "FAIL, got {} but {} expected".format(actual_res, resolution)
        )

    print("PASS")


def _switch_edid(zapper_host, edid_file, video_device):
    """Clear EDID and then 'plug' back a new monitor."""

    _clear_edid(zapper_host)
    _wait_edid_change(video_device, False)

    _set_edid(zapper_host, edid_file)
    _wait_edid_change(video_device, True)


def _set_edid(zapper_host, edid_file):
    """Request EDID change to Zapper."""
    with open(str(edid_file), "rb") as f:
        zapper_run(zapper_host, "change_edid", f.read())


def _clear_edid(zapper_host):
    """Request EDID clear to Zapper."""
    zapper_run(zapper_host, "change_edid", None)


def _check_connected(device):
    """Check if the video input device is recognized and active."""
    if os.getenv("XDG_SESSION_TYPE") == "wayland":
        cmd = ["gnome-randr", "query", device]
    else:
        cmd = ["xrandr", "--listactivemonitors"]

    randr_output = subprocess.check_output(
        cmd,
        universal_newlines=True,
        encoding="utf-8",
        stderr=subprocess.DEVNULL,
    )

    return device in randr_output


def _wait_edid_change(video_device, expected):
    """
    Wait until `expected` connection state is reached.
    Times out after 5 seconds.
    """
    iteration = 0
    max_iter = 5
    sleep = 1
    while _check_connected(video_device) != expected and iteration < max_iter:
        time.sleep(sleep)
        iteration += 1

    if iteration == max_iter:
        raise TimeoutError(
            "Reacting to the EDID change took more than {}s.".format(
                max_iter * sleep
            )
        )


def _check_resolution(video_device):
    """
    Check output resolution on target video port using randr.

    Match the randr output with a pattern to grab
    the current resolution on <video_device>.

    Both gnome-randr and xrandr highlight the currently
    selected resolution for each monitor with a `*`.

    A target string usually looks like:
    ```
    HDMI-1 connected primary 2560x1440+0+0
       2560x1440     59.91+
       1920x1080     59.91*
    ```
    where `HDMI-1` is the port and `1920x1080` is the
    resolution in use.
    """
    pattern = r"^{}.*\n.*^\s+(\d+x\d+).*\*"

    if os.getenv("XDG_SESSION_TYPE") == "wayland":
        cmd = "gnome-randr"
    else:
        cmd = "xrandr"

    randr_output = subprocess.check_output(
        [cmd],
        universal_newlines=True,
        encoding="utf-8",
        stderr=subprocess.DEVNULL,
    )

    match = re.search(
        pattern.format(video_device), randr_output, re.MULTILINE | re.DOTALL
    )

    if match:
        return match.group(1)
    return None


def main(args=None):
    """
    Test for different EDID files whether the resolution
    is recognized and selected on DUT.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Zapper IP address")
    args = parser.parse_args(args)

    try:
        video_device = discover_video_output_device(args.host)
        print("Testing EDID cycling on {}".format(video_device))
    except IOError as exc:
        raise SystemExit(
            "Cannot detect the target video output device."
        ) from exc

    failed = False

    for edid_file in EDID_FILES:
        try:
            test_edid(args.host, edid_file, video_device)
        except AssertionError as exc:
            print(exc.args[0])
            failed = True

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
