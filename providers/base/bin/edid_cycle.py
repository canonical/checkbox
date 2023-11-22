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

from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402

EDID_FILES = list(
    pathlib.Path(os.getenv("PLAINBOX_PROVIDER_DATA", ".")).glob("edids/*.edid")
)


def discover_video_output_device(zapper_host):
    """
    Try to discover the output device connected to Zapper
    checking the difference in xrandr when plugged in and
    unplugged.

    :param zapper_host: Target Zapper IP
    :return: Video Output Port, i.e. `HDMI-1`
    :raises IOError: cannot discover the video port under test
    """

    def get_active_devices():
        """Get the list of active video ouput devices."""
        if os.getenv("XDG_SESSION_TYPE") == "wayland":
            command = ["gnome-randr", "query"]
            pattern = r"^\b\w+-\d+\b"
        else:
            command = ["xrandr", "--listactivemonitors"]
            pattern = r"\b\w+-\d+\b$"

        xrandr_output = subprocess.check_output(
            command,
            universal_newlines=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        )

        return set(re.findall(pattern, xrandr_output, re.MULTILINE))

    _set_edid(zapper_host, None)

    # Not knowing what to except I can't use a busy loop here
    time.sleep(5)

    devices = get_active_devices()

    _set_edid(zapper_host, EDID_FILES[0])
    for _ in range(5):
        target = list(get_active_devices() - devices)
        if target:
            break

        time.sleep(1)
    else:
        raise IOError

    return target[0]


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

    print("checking resolution... ", end="")
    actual_res = _check_resolution(video_device)
    if actual_res != resolution:
        print("FAIL, got {} instead".format(actual_res))
        raise AssertionError()

    print("PASS")


def _switch_edid(zapper_host, edid_file, video_device):
    """Clear EDID and then 'plug' back a new monitor."""
    _set_edid(zapper_host, None)
    _wait_edid_change(video_device, False)

    _set_edid(zapper_host, edid_file)

    _wait_edid_change(video_device, True)


def _set_edid(zapper_host, edid_file=None):
    """Request EDID change to Zapper."""
    if edid_file:
        with open(edid_file, "rb") as f:
            zapper_run(zapper_host, "change_edid", f.read())
    else:
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
    while _check_connected(video_device) != expected and iteration < max_iter:
        time.sleep(1)
        iteration += 1

    if iteration == max_iter:
        raise TimeoutError


def _check_resolution(video_device):
    """
    Check output resolution on HDMI using randr.

    Match the randr output with a pattern to grab
    the current resolution on <video_device>.

    Both gnome-randr and xrandr highlight the currently
    selected resolution for each monitor with a `*`.
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
        except AssertionError:
            failed = True

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
