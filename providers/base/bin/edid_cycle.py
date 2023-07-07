#!/usr/bin/env python3
"""
This program tests whether the system changes the resolution automatically
when supplied with a new EDID information.

To run the test you need Zapper board connected and set up.

The command-line argument for the program is the address of the RaspberryPi
Host (optionally with a username), e.g.: ubuntu@192.168.1.100
"""
import os
import re
import subprocess
import sys
import time

from monitor_hotplug import check_connected

from checkbox_support.scripts.zapper_proxy import (             # noqa: E402
    zapper_run)

PATTERN = r"^HDMI-1.*\n.*^\s+(\d+x\d+).*\*"


def _match(output):
    """
    Match the given randr output with a pattern to grab
    the current resolution on HDMI-1.

    Both gnome-randr and xrandr highlight the currently
    selected resolution for each monitor with a `*`.

    xrandr
    >>> _match("Screen 0: minimum 320 x 200, current 1920 x 1080,"
    ... " maximum 16384 x 16384i\\n"
    ... "DPI-1 connected primary 1920x1080+0+0 (normal left inverted"
    ... "   1920x1080     60.00*+  59.97    59.96    59.93    40.00\\n"
    ... "HDMI-1 connected primary 1920x1080+0+0 (normal left inverted"
    ... " right x axis y axis) 309mm x 174mm\\n"
    ... "   1920x1080     60.00+  59.97    59.96    59.93    40.00\\n"
    ... "   1680x1050     59.95    59.88\\n"
    ... "   1600x1024     60.17*\\n")
    '1600x1024'

    xrandr, no output on HDMI-1
    >>> _match("Screen 0: minimum 320 x 200, current 1920 x 1080,"
    ... " maximum 16384 x 16384i\\n"
    ... "DPI-1 connected primary 1920x1080+0+0 (normal left inverted"
    ... "   1920x1080     60.00*+  59.97    59.96    59.93    40.00\\n"
    ... "HDMI-1 connected primary 1920x1080+0+0 (normal left inverted"
    ... " right x axis y axis) 309mm x 174mm\\n"
    ... "   1920x1080     60.00+  59.97    59.96    59.93    40.00\\n"
    ... "   1680x1050     59.95    59.88\\n")

    xrandr, no HDMI-1 available
    >>> _match("Screen 0: minimum 320 x 200, current 1920 x 1080,"
    ... " maximum 16384 x 16384i\\n"
    ... "DPI-1 connected primary 1920x1080+0+0 (normal left inverted"
    ... "   1920x1080     60.00*+  59.97    59.96    59.93    40.00\\n")

    gnome-randr
    >>> _match("supports-mirroring: true\\n"
    ... "layout-mode: physical\\n"
    ... "supports-changing-layout-mode: false\\n"
    ... "global-scale-required: false\\n"
    ... "legacy-ui-scaling-factor: 1\\n"
    ... 'renderer: "native"\\n\\n'
    ... "logical monitor 0:\\n"
    ... "x: 0, y: 0, scale: 1, rotation: normal, primary: yes\\n"
    ... "associated physical monitors:\\n"
    ... "	HDMI-1 DEL DELL U2722DE 4M9KFH3\\n\\n"
    ... "HDMI-1 DEL DELL U2722DE 4M9KFH3\\n"
    ... "              2560x1440@59.951	2560x1440 	59.95+"
    ... "[x1.00+, x2.00, x3.00]\\n"
    ... "              2048x1080@23.997	2048x1080 	24.00*"
    ... "[x1.00+, x2.00]\\n")
    '2048x1080'
    """
    match = re.search(PATTERN, output, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1)
    return None


def check_resolution():
    """
    Check output resolution on HDMI using randr.
    """
    if os.getenv('XDG_SESSION_TYPE') == 'wayland':
        cmd = "gnome-randr"
    else:
        cmd = "xrandr"

    randr_output = subprocess.check_output(
        [cmd],
        universal_newlines=True, encoding="utf-8")

    return _match(randr_output)


def _wait_edid_change(expected):
    """
    Wait until `expected` connection state is reached.
    Times out after 5 seconds.
    """
    iteration = 0
    max_iter = 5
    while check_connected("HDMI-1") != expected and iteration < max_iter:
        time.sleep(1)
        iteration += 1

    if iteration == max_iter:
        raise TimeoutError


def change_edid(host, edid_file):
    """Clear EDID and then 'plug' back a new monitor."""
    zapper_run(host, "change_edid", None)
    _wait_edid_change(False)

    with open(edid_file, 'rb') as f:
        zapper_run(host, "change_edid", f.read())

    _wait_edid_change(True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: {} user@edid-host'.format(sys.argv[0]))
    failed = False
    for res in ['2560x1440', '1920x1080', '1280x1024']:
        print('changing EDID to {}'.format(res))
        edid_file = os.path.expandvars(os.path.join(
            '$PLAINBOX_PROVIDER_DATA', 'edids', '{}.edid'.format(res)))

        try:
            change_edid(sys.argv[1], edid_file)
        except TimeoutError:
            print("FAIL, timed out.")
            failed = True
            continue

        print('checking resolution... ', end='')
        actual_res = check_resolution()
        if actual_res != res:
            print('FAIL, got {} instead'.format(actual_res))
            failed = True
        else:
            print('PASS')

    return failed


if __name__ == '__main__':
    raise SystemExit(main())
