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

import os
import re

from checkbox_support.parsers.kernel_cmdline import parse_kernel_cmdline
from checkbox_support.snap_utils.system import (
    get_lk_bootimg_path, add_hostfs_prefix)

# Supported bootloaders and detected files taken from:
# https://github.com/snapcore/snapd/blob/master/bootloader/bootloader.go
# name = [root dir, config file]
bootloaders = {
    'uboot': ['/boot/uboot', 'uboot.env'],
    'grub': ['/boot/grub', 'grub.cfg'],
    'androidboot': ['/boot/androidboot', 'androidboot.env'],
    'lk': ['/dev/disk/by-partlabel', 'snapbootsel']
}


def detect_bootloader():
    for name, config in bootloaders.items():
        if os.path.exists(
                os.path.join(add_hostfs_prefix(config[0]), config[1])):
            return name
    return 'unknown'


def booted_kernel_location(bl_name):
    path = 'unknown'
    type = 'unknown'
    if bl_name == 'uboot':
        pass
    elif bl_name == 'grub':
        # what about force-kernel-extract true/false ?
        type = 'fs'
        with open('/proc/cmdline', 'r') as f:
            cmdline = f.readline()
        result = parse_kernel_cmdline(cmdline)
        grub_path = result.params['BOOT_IMAGE']

        # The BOOT_IMAGE parameter is tricky to decipher. It can be absolute
        # path or refer or contain a variable expanded by ... initramfs?
        if os.path.isabs(grub_path):
            path = grub_path
        else:
            try:
                # if we know where the parameter is referencing, replace it
                if '(loop)' in grub_path:
                    # implies of out of the kernel snap (so no FDE)
                    pass
                elif re.search(r'\(hd\d,gpt\d\)', grub_path, re.M):
                    # used by fortknox, vasteras,...
                    path = os.path.join(
                        '/boot/efi', grub_path[grub_path.index(')')+2:])
            except ValueError:
                pass
    elif bl_name == 'androidboot':
        pass
    elif bl_name == 'lk':
        type = 'raw'
        path = get_lk_bootimg_path()
    return (path, type)


if __name__ == "__main__":
    bl_name = detect_bootloader()
    print('name: {}'.format(bl_name))
    path, type = booted_kernel_location(bl_name)
    print('booted_kernel_path: {}'.format(path))
    print('booted_kernel_partition_type: {}'.format(type))
    print()
