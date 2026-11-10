#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

import errno
import os
import sys
import time


def export_gpio(lane):
    try:
        with open("/sys/class/gpio/export", "w") as f_export:
            f_export.write(f"{lane}\n")
    except OSError as e:
        if e.errno == errno.EBUSY:
            # EBUSY indicates GPIO already exported
            print(f"GPIO {lane} already exported")
            pass
        else:
            sys.stderr.write(f"Failed request to export GPIO {lane}\n")
            raise
    # test directory exists
    if not os.path.exists(f"/sys/class/gpio/gpio{lane}"):
        raise SystemExit(f"GPIO {lane} failed to export")


def unexport_gpio(lane):
    try:
        with open("/sys/class/gpio/unexport", "w") as f_unexport:
            f_unexport.write(f"{lane}\n")
    except OSError:
        sys.stderr.write(f"Failed request to unexport GPIO {lane}\n")
        raise
    # test directory removed
    if os.path.exists(f"/sys/class/gpio/gpio{lane}"):
        raise SystemExit(f"GPIO {lane} failed to export")


def configure_gpio(lane, direction):
    with open(f"/sys/class/gpio/gpio{lane}/direction", "w") as f:
        f.write(f"{direction}\n")


def write_gpio(lane, val):
    with open(f"/sys/class/gpio/gpio{lane}/value", "w") as f:
        f.write(f"{val}\n")


def read_gpio(lane):
    with open(f"/sys/class/gpio/gpio{lane}/value") as f:
        return f.read().strip()


def loopback_test(out_lane, in_lane):
    print(f"{out_lane} -> {in_lane}", flush=True)
    export_gpio(out_lane)
    configure_gpio(out_lane, "out")
    export_gpio(in_lane)
    configure_gpio(in_lane, "in")
    for i in range(6):
        write_gpio(out_lane, i % 2)
        time.sleep(0.5)
        if read_gpio(in_lane) != str(i % 2):
            raise SystemExit(
                f"Failed loopback test out: {out_lane} in: {in_lane}"
            )
        time.sleep(0.5)
    unexport_gpio(out_lane)
    unexport_gpio(in_lane)


def gpio_pairs(model_name):
    gpio_data = os.path.expandvars(
        f"$PLAINBOX_PROVIDER_DATA/gpio-loopback.{model_name}.in"
    )
    if not os.path.exists(gpio_data):
        raise SystemExit(f"ERROR: no gpio information found at: {gpio_data}")
    with open(gpio_data) as f:
        for line in f:
            if line.startswith("#"):
                continue
            yield line.strip().split(",")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: gpio_syfs_loopback.py MODEL_NAME")
    model_name = sys.argv[1]
    for pair in gpio_pairs(model_name):
        loopback_test(*pair)


if __name__ == "__main__":
    main()
