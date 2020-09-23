#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2019 Canonical Ltd.
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

import contextlib
import os
import re

from checkbox_support.parsers.kernel_cmdline import parse_kernel_cmdline
from checkbox_support.snap_utils.system import get_lk_bootimg_path
from checkbox_support.snap_utils.system import add_hostfs_prefix
from checkbox_support.snap_utils.system import get_series


# Supported bootloaders and detected files taken from:
# https://github.com/snapcore/snapd/blob/master/bootloader/bootloader.go
# name = [root dir, config file]
if int(get_series()) >= 20:
    bootloaders = {
        'uboot': ['/boot/uboot', 'boot.sel'],
        'grub': ['/boot/grub', 'grub.cfg'],
        'androidboot': ['/boot/androidboot', 'androidboot.env'],
        'lk': ['/dev/disk/by-partlabel', 'snapbootsel']
    }
else:
    bootloaders = {
        'uboot': ['/boot/uboot', 'uboot.env'],
        'grub': ['/boot/grub', 'grub.cfg'],
        'androidboot': ['/boot/androidboot', 'androidboot.env'],
        'lk': ['/dev/disk/by-partlabel', 'snapbootsel']
    }


def detect_bootloader():
    for name, config in bootloaders.items():
        path = os.path.join(add_hostfs_prefix(config[0]), config[1])
        if os.path.exists(path):
            return name
    return 'unknown'


def booted_kernel_location(bl_name):
    """Get kernel location returning (path, type) tuple.

    Path: either file path or partition name (see type)
    Type: how the kernel is stored on the storage medium. Either: 'fs' for file
      on a regular filesystem, or 'raw' for directly at a partition location

    If either is not indentifiable currently use value 'unknown'.
    """
    if bl_name == 'grub':
        if int(get_series()) >= 20:
            symlink = '/boot/grub/kernel.efi'
            prefixed = add_hostfs_prefix(symlink)
            path = os.path.realpath(prefixed)
            if symlink != prefixed:
                path = path[len(prefixed.rsplit(symlink, 1)[0]):]
            return (path, 'fs')

        # The BOOT_IMAGE kernmel cmdline parameter is tricky to decipher. It
        # can be an absolute path or refer or contain a variable expanded by
        # ... initramfs? Tested on fortknox, vasteras projects.
        with open('/proc/cmdline', 'r') as f:
            cmdline = f.readline()
        result = parse_kernel_cmdline(cmdline)
        grub_path = result.params.get('BOOT_IMAGE')
        if grub_path:
            if os.path.isabs(grub_path):
                return(grub_path, 'fs')
            with contextlib.suppress(ValueError):
                # if we know where the parameter is referencing,
                # replace it
                if re.search(r'\(hd\d,gpt\d\)', grub_path, re.M):
                    path = os.path.join(
                        '/boot/efi', grub_path[grub_path.index(')')+2:])
                    return(path, 'fs')
        return ('unknown', 'fs')
    elif bl_name == 'lk':
        return(get_lk_bootimg_path(), 'raw')
    return ('unknown', 'unknown')  # bl_name in ('uboot', 'androidboot')


if __name__ == "__main__":
    bl_name = detect_bootloader()
    print('name: {}'.format(bl_name))
    path, type = booted_kernel_location(bl_name)
    print('booted_kernel_path: {}'.format(path))
    print('booted_kernel_partition_type: {}'.format(type))
    print()
