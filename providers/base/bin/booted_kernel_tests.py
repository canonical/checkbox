#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

import hashlib
import os
import sys

from checkbox_support.snap_utils.system import get_kernel_snap
from checkbox_support.snap_utils.system import get_series
from checkbox_support.snap_utils.system import add_hostfs_prefix

# 64kb buffer, hopefully suitable for all devices that might run this test
BUF_SIZE = 65536


def get_snap_kernel_path():
    kernel = get_kernel_snap()
    if kernel is None:
        raise SystemExit('ERROR: failed to get kernel snap')
    if int(get_series()) >= 20:
        path = '/snap/{}/current/kernel.efi'.format(kernel)
    else:
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


def kernel_matches_current(booted_kernel_image):
    rh = get_hash(booted_kernel_image)
    print('Running kernel hash:\n', rh, '\n')
    snap_kernel_image = get_snap_kernel_path()
    print('Snap kernel image: {}'.format(snap_kernel_image))
    sh = get_hash(snap_kernel_image)
    print('Current kernel snap hash:\n', sh, '\n')
    if rh != sh:
        print('ERROR: hashes do not match')
        return 1
    print('Hashes match')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('ERROR: please specify the path to booted kernel')
    booted_kernel_image = sys.argv[1]

    print('Supplied booted kernel image: {}'.format(booted_kernel_image))
    prefixed_image = add_hostfs_prefix(booted_kernel_image)

    if not os.path.exists(prefixed_image):
        raise SystemExit('ERROR: invalid path to booted kernel supplied')

    sys.exit(kernel_matches_current(prefixed_image))
