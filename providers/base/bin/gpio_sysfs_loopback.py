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
        with open('/sys/class/gpio/export', 'w') as f_export:
            f_export.write('{}\n'.format(lane))
    except OSError as e:
        if e.errno == errno.EBUSY:
            # EBUSY indicates GPIO already exported
            print('GPIO {} already exported'.format(lane))
            pass
        else:
            sys.stderr.write('Failed request to export GPIO {}\n'.format(lane))
            raise
    # test directory exists
    if not os.path.exists('/sys/class/gpio/gpio{}'.format(lane)):
        raise SystemExit('GPIO {} failed to export'.format(lane))


def unexport_gpio(lane):
    try:
        with open('/sys/class/gpio/unexport', 'w') as f_unexport:
            f_unexport.write('{}\n'.format(lane))
    except OSError:
        sys.stderr.write('Failed request to unexport GPIO {}\n'.format(lane))
        raise
    # test directory removed
    if os.path.exists('/sys/class/gpio/gpio{}'.format(lane)):
        raise SystemExit('GPIO {} failed to export'.format(lane))


def configure_gpio(lane, direction):
    with open('/sys/class/gpio/gpio{}/direction'.format(lane), 'wt') as f:
        f.write('{}\n'.format(direction))


def write_gpio(lane, val):
    with open('/sys/class/gpio/gpio{}/value'.format(lane), 'wt') as f:
        f.write('{}\n'.format(val))


def read_gpio(lane):
    with open('/sys/class/gpio/gpio{}/value'.format(lane), 'r') as f:
        return f.read().strip()


def loopback_test(out_lane, in_lane):
    print("{} -> {}".format(out_lane, in_lane), flush=True)
    export_gpio(out_lane)
    configure_gpio(out_lane, 'out')
    export_gpio(in_lane)
    configure_gpio(in_lane, 'in')
    for i in range(6):
        write_gpio(out_lane, i % 2)
        time.sleep(0.5)
        if read_gpio(in_lane) != str(i % 2):
            raise SystemExit("Failed loopback test out: {} in: {}".format(
                out_lane, in_lane))
        time.sleep(0.5)
    unexport_gpio(out_lane)
    unexport_gpio(in_lane)


def gpio_pairs(model_name):
    gpio_data = os.path.expandvars(
        '$PLAINBOX_PROVIDER_DATA/gpio-loopback.{}.in'.format(model_name))
    if not os.path.exists(gpio_data):
        raise SystemExit(
            "ERROR: no gpio information found at: {}".format(gpio_data))
    with open(gpio_data, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            yield line.strip().split(',')


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: gpio_syfs_loopback.py MODEL_NAME')
    model_name = sys.argv[1]
    for pair in gpio_pairs(model_name):
        loopback_test(*pair)


if __name__ == '__main__':
    main()
