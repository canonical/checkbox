#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
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

import filecmp
import sys
from os import walk
from os.path import join, relpath

from checkbox_support.snap_utils.system import get_kernel_snap


if len(sys.argv) != 2:
    raise SystemExit('ERROR: please specify the bootloader')

dtb_dir = '/var/lib/snapd/hostfs/boot/{}'.format(sys.argv[1])
print('Bootloader DTB location: {}'.format(dtb_dir))

kernel = get_kernel_snap()
if kernel is None:
    raise SystemExit('ERROR: failed to get kernel snap')
snap_dtbs = '/snap/{}/current/dtbs'.format(kernel)
print('Kernel snap DTB location: {}'.format(
    snap_dtbs), end='\n\n', flush=True)

snap_files = []
for (dirpath, dirs, files) in walk(snap_dtbs):
    if dirpath == snap_dtbs:
        snap_files.extend(files)
    else:
        snap_files.extend([join(relpath(dirpath, snap_dtbs), f)
                           for f in files])

match, mismatch, errors = filecmp.cmpfiles(
    snap_dtbs, dtb_dir, snap_files, shallow=True)

if match:
    print('{} matching DTB files found'.format(
        len(match)), end='\n\n', flush=True)

if mismatch:
    print('FAIL: DTB files shipped in kernel snap with mismatched versions'
          ' in bootloader dir:', file=sys.stderr)
    for f in mismatch:
        print(f, file=sys.stderr)
    print('', file=sys.stderr, flush=True)

if errors:
    print('FAIL: DTB files shipped in kernel snap which could not be'
          ' found in bootloader dir:', file=sys.stderr)
    for f in errors:
        print(f, file=sys.stderr)
    print('', file=sys.stderr, flush=True)

if mismatch or errors:
    raise SystemExit('Comparison failed')
