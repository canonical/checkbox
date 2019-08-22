#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

import hashlib
import sys

from checkbox_support.snap_utils.system import get_kernel_snap
from checkbox_support.snap_utils.system import get_bootloader

# 64kb buffer, hopefully suitable for all devices that might run this test
BUF_SIZE = 65536


def get_running_kernel_path():
    bootloader = get_bootloader()
    if bootloader is None:
        raise SystemExit('ERROR: failed to get bootloader')
    path = '/boot/{}/kernel.img'.format(bootloader)
    return path


def get_snap_kernel_path():
    kernel = get_kernel_snap()
    if kernel is None:
        raise SystemExit('ERROR: failed to get kernel snap')
    path = '/snap/{}/current/kernel.img'.format(kernel)
    return path


def get_hash(path):
    sha1 = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def kernel_matches_current():
    rh = get_hash(get_running_kernel_path())
    print('Running kernel hash:\n', rh, '\n')
    sh = get_hash(get_snap_kernel_path())
    print('Current kernel snap hash:\n', sh, '\n')
    if rh != sh:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(kernel_matches_current())
