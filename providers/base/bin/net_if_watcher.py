#!/usr/bin/env python3
# Copyright 2018 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
"""
Detect insertion of a new network interface.
"""

from pathlib import Path
import time


def get_ifaces():
    return set([i.name for i in Path("/sys/class/net").iterdir()])


def main():
    print("INSERT NOW")
    starting_ifaces = get_ifaces()
    attempts = 20
    while attempts > 0:
        now_ifaces = get_ifaces()
        # check if something disappeared
        if not starting_ifaces == now_ifaces & starting_ifaces:
            raise SystemExit("Interface(s) disappeared: {}".format(
                ", ".join(list(starting_ifaces - now_ifaces))))
        new_ifaces = now_ifaces - starting_ifaces
        if new_ifaces:
            print()
            print("New interface(s) detected: {}".format(
                ", ".join(list(new_ifaces))))
            return
        time.sleep(1)
        print('.', end='', flush=True)
        attempts -= 1
    print()
    raise SystemExit("Failed to detect new network interface")


if __name__ == '__main__':
    main()
