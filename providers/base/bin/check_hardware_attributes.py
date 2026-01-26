#!/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
import os
import multiprocessing
import sys


def try_read_node(path):
    """
    Attempts to read a single sysfs attribute.
    Isolated in a subprocess to protect against D-state hangs.
    """
    try:
        with open(path, "r") as f:
            # only need the first byte to trigger the kernel 'show' function
            f.read(1)
    except Exception:
        pass


def walk_devices(base_path="/sys/devices", timeout=10.0):

    # use os.walk but skip non-device directories if necessary
    failed = 0
    for root, dirs, files in os.walk(base_path):
        for name in files:
            full_path = os.path.join(root, name)

            # Skip known 'noisy' or non-hardware files to be efficient
            if name in ["uevent", "modalias", "resource"]:
                continue

            if os.access(full_path, os.R_OK):
                p = multiprocessing.Process(
                    target=try_read_node, args=(full_path,)
                )
                p.start()
                p.join(timeout)

                if p.is_alive():
                    failed = 1
                    print(full_path)
                    p.terminate()
                    p.join()
                # We stay silent on success to highlight the problem areas
    return failed


if __name__ == "__main__":
    print(
        "Scanning /sys/devices for unresponsive attributes (Timeout: 10s)..."
    )
    sys.exit(walk_devices())
