#!/usr/bin/env python3
"""
"""

import os
import subprocess
import sys
import time

from checkbox_support.scripts.zapper_proxy import (             # noqa: E402
    ControlVersionDecider)


def _check_hdmi_connected(index):
    xrandr = subprocess.check_output("xrandr", encoding="utf-8")
    hdmi = next(line for line in xrandr if f"HDMI-{index}" in line)
    return "connected" in hdmi


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: {} hdmi-host hdmi-index'.format(sys.argv[0]))

    failed = False
    zapper_control = ControlVersionDecider().decide(sys.argv[1])
    edid_file = os.path.expandvars(os.path.join(
        '$PLAINBOX_PROVIDER_DATA', 'edids', '1920x1080.edid'))

    print("unplugging HDMI... ", end="")
    zapper_control.change_edid(None)
    if _check_hdmi_connected(sys.argv[2]) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("plugging HDMI... ", end="")
    with open(edid_file, 'rb') as f:
        zapper_control.change_edid(f.read())
    time.sleep(5)
    if _check_hdmi_connected(sys.argv[2]) is True:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    print("unplugging HDMI... ", end="")
    zapper_control.change_edid(None)
    if _check_hdmi_connected(sys.argv[2]) is False:
        print("PASS")
    else:
        failed = True
        print("FAILED")

    return failed
