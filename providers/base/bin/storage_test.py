#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#
# Perfrom bonnie++ disk test

from collections import namedtuple
from contextlib import ExitStack
import os
import subprocess as sp
import sys
import tempfile

import psutil


def mountpoint(device):
    for part in psutil.disk_partitions():
        if part.device == device:
            return part.mountpoint
    return None


def find_largest_partition(device):
    BlkDev = namedtuple('BlkDev', ['name', 'size', 'type', 'fstype'])
    cmd = 'lsblk -b -l -n -o NAME,SIZE,TYPE,FSTYPE {}'.format(device)
    out = sp.check_output(cmd, shell=True)
    blk_devs = []
    for entry in out.decode(sys.stdout.encoding).splitlines():
        params = entry.strip().split()
        if len(params) == 3:
            # filesystem info missing, so it's unknown
            params.append(None)
        blk_devs.append(BlkDev(*params))
    blk_devs[:] = [bd for bd in blk_devs if (
        bd.type in ('part', 'md') and bd.fstype is not None)]
    if not blk_devs:
        raise SystemExit(
            'ERROR: No suitable partitions found on device {}'.format(device))
    blk_devs.sort(key=lambda bd: int(bd.size))
    return blk_devs[-1].name


def mount(source, target):
    cmd = 'mount {} {}'.format(source, target)
    print('+', cmd, flush=True)
    sp.check_call(cmd, shell=True)


def unmount(target):
    cmd = 'umount {}'.format(target)
    print('+', cmd, flush=True)
    sp.check_call(cmd, shell=True)


def memory():
    return psutil.virtual_memory().total / (1024 * 1024)


def free_space(test_dir):
    du = psutil.disk_usage(test_dir)
    return du.free / (1024 * 1024)


def devmapper_name(udev_name):
    dm_name = None
    sys_d = '/sys/block/{}'.format(udev_name)
    if os.path.isdir(os.path.join(sys_d, 'dm')):
        with open('/sys/block/{}/dm/name'.format(udev_name), 'r') as f:
            dm_name = f.read().strip()
    return dm_name


def run_bonnie(test_dir, user='root'):
    # Set a maximum size on the amount of RAM, this has the effect of keeping
    # the amount of data written during tests lower than default. This keeps
    # duration of tests at something reasonable
    force_mem_mb = 8000
    if memory() < force_mem_mb:
        force_mem_mb = memory()
    # When running on disks with small drives (SSD/flash) we need to do
    # some tweaking. Bonnie uses 2x RAM by default to write data. If that's
    # more than available disk space, the test will fail inappropriately.
    free = free_space(test_dir)
    print('{}MB of free space avaialble'.format(free))
    if (force_mem_mb * 2) > free:
        force_mem_mb = free / 4
    print('Forcing memory setting to {}MB'.format(force_mem_mb))
    cmd = 'bonnie++ -d {} -u {} -r {}'.format(test_dir, user, force_mem_mb)
    print('+', cmd, flush=True)
    sp.check_call(cmd, shell=True)


def devmapper_test(udev_name):
    print('identified as a devmapper device...')
    device = '/dev/{}'.format(udev_name)
    mount_dir = mountpoint(device)
    if mount_dir:
        print('{} already mounted at {}'.format(device, mount_dir))
    else:
        dm_name = devmapper_name(udev_name)
        if dm_name:
            dm_device = os.path.join('/dev/mapper', dm_name)
            if os.path.exists(dm_device):
                mount_dir = mountpoint(dm_device)
                if mount_dir:
                    print('{} already mounted at {}'.format(
                        dm_device, mount_dir))
    with ExitStack() as stack:
        if mount_dir is None:
            mount_dir = tempfile.mkdtemp()
            stack.callback(os.rmdir, mount_dir)
            mount(device, mount_dir)
            print('Performed mount of {} at {}'.format(device, mount_dir))
            stack.callback(unmount, mount_dir)
        run_bonnie(mount_dir)


def disk_test(udev_name):
    print('identified as a disk...')
    device = '/dev/{}'.format(udev_name)
    part_to_test = '/dev/{}'.format(find_largest_partition(device))
    print('test will be run on partition {}'.format(part_to_test))
    mount_dir = mountpoint(part_to_test)
    if mount_dir:
        print('{} already mounted at {}'.format(part_to_test, mount_dir))
    with ExitStack() as stack:
        if mount_dir is None:
            mount_dir = tempfile.mkdtemp()
            stack.callback(os.rmdir, mount_dir)
            mount(part_to_test, mount_dir)
            print('Performed mount {} at {}'.format(part_to_test, mount_dir))
            stack.callback(unmount, mount_dir)
        run_bonnie(mount_dir)


def main():
    udev_name = sys.argv[1]
    print('Testing disk {}'.format(udev_name))

    # handle dev mapper and regular disks seperately
    if devmapper_name(udev_name):
        devmapper_test(udev_name)
    else:
        disk_test(udev_name)


if __name__ == "__main__":
    main()
