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
        if os.path.exists(os.path.join(config[0], config[1])):
            return name
    return 'unknown'


if __name__ == "__main__":
    bl_name = detect_bootloader()
    print('name: {}'.format(bl_name))
    print()
