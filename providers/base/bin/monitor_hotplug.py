#!/usr/bin/env python3
"""
This program tests whether the system recognizes a hotplug event
from a certain video peripheral (HDMI, DP, ...).

To run the test you need Zapper board connected and set up.
"""

import argparse
import os
import subprocess
import time

from checkbox_support.scripts.zapper_proxy import (  # noqa: E402
    zapper_run)


def check_connected(device):
    if os.getenv('XDG_SESSION_TYPE') == 'wayland':
        xrandr_output = subprocess.check_output(
            ["gnome-randr", "query", device],
            universal_newlines=True, encoding="utf-8")
    else:
        xrandr_output = subprocess.check_output(
            ["xrandr", "--listactivemonitors"],
            universal_newlines=True, encoding="utf-8")
    return device in xrandr_output


def _change_hdmi_status(zapper_host, status):
    edid_file = os.path.expandvars(os.path.join(
        '$PLAINBOX_PROVIDER_DATA', 'edids', '1920x1080.edid'))
    if status == "connected":
        with open(edid_file, 'rb') as edid_bin:
            zapper_run(zapper_host, "change_edid", edid_bin.read())
    else:
        zapper_run(zapper_host, "change_edid", None)
    time.sleep(5)


_change_fn = {
    "hdmi": _change_hdmi_status,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("peripheral", choices=["hdmi"])
    parser.add_argument("index")
    parser.add_argument("host", help="Zapper IP address")
    args = parser.parse_args()

    failed = False
    device = "{}-{}".format(
            args.peripheral.upper(), args.index)

    print("unplugging {}... ".format(args.peripheral), end="")
    _change_fn[args.peripheral](args.host, "disconnected")
    if check_connected(device) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("plugging {}... ".format(args.peripheral), end="")
    _change_fn[args.peripheral](args.host, "connected")
    if check_connected(device) is True:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("unplugging {}... ".format(args.peripheral), end="")
    _change_fn[args.peripheral](args.host, "disconnected")
    if check_connected(device) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    return failed


if __name__ == '__main__':
    raise SystemExit(main())
