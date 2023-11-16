#!/usr/bin/env python3
"""
This program tests whether the system recognizes a hotplug event
from a certain video peripheral (HDMI, DP, ...).

To run the test you need Zapper board connected and set up.
"""

import argparse
import os
import re
import subprocess
import time

from checkbox_support.scripts.zapper_proxy import (             # noqa: E402
    zapper_run)


def discover_video_output_device(zapper_host):
    """
    Try to discover the output device connected to Zapper
    checking the difference in xrandr when plugged in and
    unplugged.
    """

    def get_active_devices():
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
        )

        return set(re.findall(pattern, xrandr_output, re.MULTILINE))

    _change_status(zapper_host, "disconnected")
    devices = get_active_devices()

    _change_status(zapper_host, "connected")
    for _ in range(5):
        target = list(get_active_devices() - devices)
        if target:
            break

        time.sleep(1)
    else:
        raise FileNotFoundError

    return target[0]


def check_connected(device):
    if os.getenv("XDG_SESSION_TYPE") == "wayland":
        xrandr_output = subprocess.check_output(
            ["gnome-randr", "query", device], universal_newlines=True, encoding="utf-8"
        )
    else:
        xrandr_output = subprocess.check_output(
            ["xrandr", "--listactivemonitors"],
            universal_newlines=True,
            encoding="utf-8",
        )
    return device in xrandr_output


def _change_status(zapper_host, status):
    edid_file = os.path.expandvars(
        os.path.join("$PLAINBOX_PROVIDER_DATA", "edids", "1920x1080.edid")
    )
    if status == "connected":
        with open(edid_file, "rb") as edid_bin:
            zapper_run(zapper_host, "change_edid", edid_bin.read())
    else:
        zapper_run(zapper_host, "change_edid", None)
    time.sleep(5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Zapper IP address")
    args = parser.parse_args()

    failed = False

    try:
        video_device = discover_video_output_device(args.host)
    except FileNotFoundError as exc:
        raise SystemExit("Cannot detect the target video output device.")
    print("unplugging {}... ".format(video_device), end="")
    _change_status(args.host, "disconnected")
    if check_connected(video_device) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("plugging {}... ".format(video_device), end="")
    _change_status(args.host, "connected")
    if check_connected(video_device) is True:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("unplugging {}... ".format(video_device), end="")
    _change_status(args.host, "disconnected")
    if check_connected(video_device) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
