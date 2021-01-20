#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
"""Check if hotplugging works on an ethernet port."""

import sys
import time


def has_cable(iface):
    """Check if cable is inserted in the ethernet port identified by iface."""
    path = '/sys/class/net/{}/carrier'.format(iface)
    with open(path) as carrier:
        return carrier.read()[0] == '1'


def main():
    """Entry point to the program."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage {} INTERFACE_NAME".format(sys.argv[0]))
    iface = sys.argv[1]
    # sanity check of the interface path
    try:
        has_cable(iface)
    except Exception as exc:
        msg = "Could not check the cable for '{}': {}".format(iface, exc)
        raise SystemExit(msg) from exc
    print(("Press enter and unplug the ethernet cable "
           "from the port {} of the System.").format(iface))
    print("After 15 seconds plug it back in.")
    print("Checkbox session may be interrupted but it should come back up.")
    input()
    print("Waiting for cable to get disconnected.")
    elapsed = 0
    while elapsed < 60:
        if not has_cable(sys.argv[1]):
            break
        time.sleep(1)
        print(".", flush=True, end='')
        elapsed += 1
    else:
        raise SystemExit("Failed to detect unplugging!")
    print("Cable unplugged!")
    print("Waiting for the cable to get connected.")
    elapsed = 0
    while elapsed < 60:
        if has_cable(sys.argv[1]):
            break
        time.sleep(1)
        print(".", flush=True, end='')
        elapsed += 1
    else:
        raise SystemExit("Failed to detect plugging it back!")
    print("Cable detected!")


if __name__ == '__main__':
    main()
