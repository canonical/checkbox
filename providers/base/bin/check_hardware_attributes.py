#!/bin/env python3
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
            # We only need the first byte to trigger the kernel 'show' function
            f.read(1)
    except Exception:
        pass


def walk_devices(base_path="/sys/devices", timeout=10.0):

    # We use os.walk but skip non-device directories if necessary
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
