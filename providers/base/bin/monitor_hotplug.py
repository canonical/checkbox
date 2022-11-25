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
    ControlVersionDecider)


def _check_hdmi_connected(index):
    xrandr = subprocess.check_output("xrandr", encoding="utf-8")
    hdmi = next(
        line for line in xrandr.splitlines() if "HDMI-{}".format(index) in line
    )
    return "disconnected" not in hdmi


def _change_hdmi_status(zapper_control, status):
    edid_file = os.path.expandvars(os.path.join(
        '$PLAINBOX_PROVIDER_DATA', 'edids', '1920x1080.edid'))
    if status == "connected":
        with open(edid_file, 'rb') as edid_bin:
            zapper_control.change_edid(edid_bin.read())
        time.sleep(5)
    else:
        zapper_control.change_edid(None)


_check_fn = {
    "hdmi": _check_hdmi_connected,
}

_change_fn = {
    "hdmi": _change_hdmi_status,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("peripheral", choices=["hdmi"])
    parser.add_argument("index")
    parser.add_argument("host", help="Zapper IP address")
    args = parser.parse_args()

    zapper_control = ControlVersionDecider().decide(args.host)

    failed = False
    print("unplugging {}... ".format(args.peripheral), end="")
    _change_fn[args.peripheral](zapper_control, "disconnected")
    if _check_fn[args.peripheral](args.index) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("plugging {}... ".format(args.peripheral), end="")
    _change_fn[args.peripheral](zapper_control, "connected")
    if _check_fn[args.peripheral](args.index) is True:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("unplugging {}... ".format(args.peripheral), end="")
    _change_fn[args.peripheral](zapper_control, "disconnected")
    if _check_fn[args.peripheral](args.index) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    return failed


if __name__ == '__main__':
    raise SystemExit(main())
