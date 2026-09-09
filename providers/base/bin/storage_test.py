#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#
# Perform bonnie++ disk test

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
    BlkDev = namedtuple("BlkDev", ["name", "size", "type", "fstype"])
    cmd = f"lsblk -b -l -n -o NAME,SIZE,TYPE,FSTYPE {device}"
    out = sp.check_output(cmd, shell=True)
    blk_devs = []
    for entry in out.decode(sys.stdout.encoding).splitlines():
        params = entry.strip().split()
        if len(params) == 3:
            # filesystem info missing, so it's unknown - skip
            continue
        blk_devs.append(BlkDev(*params))
    blk_devs[:] = [
        bd
        for bd in blk_devs
        if (bd.type in ("part", "md") and bd.fstype != "crypto_LUKS")
    ]
    if not blk_devs:
        raise SystemExit(
            f"ERROR: No suitable partitions found on device {device}"
        )
    blk_devs.sort(key=lambda bd: int(bd.size))
    return blk_devs[-1].name


def mount(source, target):
    cmd = f"mount {source} {target}"
    print("+", cmd, flush=True)
    sp.check_call(cmd, shell=True)


def unmount(target):
    cmd = f"umount {target}"
    print("+", cmd, flush=True)
    sp.check_call(cmd, shell=True)


def memory():
    return psutil.virtual_memory().total / (1024 * 1024)


def free_space(test_dir):
    du = psutil.disk_usage(test_dir)
    return du.free / (1024 * 1024)


def devmapper_name(udev_name):
    dm_name = None
    sys_d = f"/sys/block/{udev_name}"
    if os.path.isdir(os.path.join(sys_d, "dm")):
        with open(f"/sys/block/{udev_name}/dm/name") as f:
            dm_name = f.read().strip()
    return dm_name


def run_bonnie(test_dir, user="root"):
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
    print(f"{free}MB of free space available")
    if (force_mem_mb * 2) > free:
        force_mem_mb = free / 4
    print(f"Forcing memory setting to {force_mem_mb}MB")
    cmd = f"bonnie++ -d {test_dir} -u {user} -r {force_mem_mb}"
    print("+", cmd, flush=True)
    sp.check_call(cmd, shell=True)


def devmapper_test(udev_name):
    print("identified as a devmapper device...")
    device = f"/dev/{udev_name}"
    mount_dir = mountpoint(device)
    if mount_dir:
        print(f"{device} already mounted at {mount_dir}")
    else:
        dm_name = devmapper_name(udev_name)
        if dm_name:
            dm_device = os.path.join("/dev/mapper", dm_name)
            if os.path.exists(dm_device):
                mount_dir = mountpoint(dm_device)
                if mount_dir:
                    print(f"{dm_device} already mounted at {mount_dir}")
    with ExitStack() as stack:
        if mount_dir is None:
            mount_dir = tempfile.mkdtemp()
            stack.callback(os.rmdir, mount_dir)
            mount(device, mount_dir)
            print(f"Performed mount of {device} at {mount_dir}")
            stack.callback(unmount, mount_dir)
        run_bonnie(mount_dir)


def disk_test(udev_name):
    print("identified as a disk...")
    device = f"/dev/{udev_name}"
    part_to_test = f"/dev/{find_largest_partition(device)}"
    print(f"test will be run on partition {part_to_test}")
    mount_dir = mountpoint(part_to_test)
    if mount_dir:
        print(f"{part_to_test} already mounted at {mount_dir}")
    with ExitStack() as stack:
        if mount_dir is None:
            mount_dir = tempfile.mkdtemp()
            stack.callback(os.rmdir, mount_dir)
            mount(part_to_test, mount_dir)
            print(f"Performed mount {part_to_test} at {mount_dir}")
            stack.callback(unmount, mount_dir)
        run_bonnie(mount_dir)


def main():
    udev_name = sys.argv[1]
    print(f"Testing device {udev_name}")

    # Handle devmapper, and regular disks separately, and ignore mtdblock.
    if udev_name.startswith("mtdblock"):
        print("Ignoring mtdblock device")
    elif devmapper_name(udev_name):
        devmapper_test(udev_name)
    else:
        disk_test(udev_name)


if __name__ == "__main__":
    main()
