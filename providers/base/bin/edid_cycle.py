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

from checkbox_support.scripts.zapper_proxy import (             # noqa: E402
    zapper_run)

PATTERN = "^HDMI-1.*\n.* (\\d+x\\d+).*\\*"


def check_resolution():
    """
    Check output resolution on HDMI using randr.
    Both gnome-randr and xrandr highlight the currently
    selected resolution for each monitor with a `*`.
    """
    if os.getenv('XDG_SESSION_TYPE') == 'wayland':
        cmd = "gnome-randr"
    else:
        cmd = "xrandr"

    randr_output = subprocess.check_output([cmd],
        universal_newlines=True, encoding="utf-8")

    match = re.search(PATTERN, randr_output, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1)
    else:
        return None



def change_edid(host, edid_file):
    """Clear EDID and then 'plug' back a new monitor."""
    zapper_run(host, "change_edid", None)
    time.sleep(1)
    with open(edid_file, 'rb') as f:
        zapper_run(host, "change_edid", f.read())


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: {} user@edid-host'.format(sys.argv[0]))
    failed = False
    for res in ['2560x1440', '1920x1080', '1280x1024']:
        print('changing EDID to {}'.format(res))
        edid_file = os.path.expandvars(os.path.join(
            '$PLAINBOX_PROVIDER_DATA', 'edids', '{}.edid'.format(res)))
        change_edid(sys.argv[1], edid_file)
        time.sleep(5)
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
