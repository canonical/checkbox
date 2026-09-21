#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Zhongning Li <zhongning.li@canonical.com>
#
# Perform bonnie++ disk test

import json
import os
import subprocess as sp
import sys
import tempfile
from argparse import ArgumentParser
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import psutil

ACCEPTED_DEVICE_TYPES = ("part", "md")


class BlockDevice(NamedTuple):
    # warning: these types are not enforced without explicit checks at runtime
    name: str  # nvme0n1p3, dm_crypt-0
    size: int
    type: str  # lvm, part, crypt
    fstype: str  # ext4, vfat, crypto_LUKS


def get_mountable_fstypes() -> "list[str]":
    """
    from 'man 8 mount'

    If no -t option is given, or if the auto type is specified,
    mount will try to guess the desired type. mount uses the
    libblkid(3) library for guessing the filesystem type; if that
    does not turn up anything that looks familiar, mount will try
    to read the file /etc/filesystems, or, if that does not exist,
    /proc/filesystems. All of the filesystem types listed there
    will be tried, except for those that are labeled "nodev" (e.g.
    devpts, proc and nfs).
    """
    proc_filesystems_raw = Path("/proc/filesystems").read_text()
    mountable_fstypes: "list[str]" = []
    for line in proc_filesystems_raw.splitlines():
        words = line.strip().split()
        if len(words) == 1:
            # each line is either just the fstype or starts with "nodev"
            # examples:
            # nodev	debugfs <--- not mountable
            # ext4 <--- mountable

            # every line with nodev is unmountable
            # because they are not disk-backed filesystems, so we skip them
            mountable_fstypes.append(words[0])
    return mountable_fstypes


def mountpoint(device: Path) -> "Path | None":
    for part in psutil.disk_partitions():
        if Path(part.device).resolve() == device.resolve():
            return Path(part.mountpoint)
    return None


def find_largest_partition(device: Path) -> Path:
    out = json.loads(
        sp.check_output(
            [
                "lsblk",
                # available on 18.04+
                "--json",
                # makes SIZE always an integer
                "--bytes",
                # flatten the output,
                # so we don't need to walk the tree
                "--list",
                # filter these columns
                # return null when value unavailable
                "--output",
                "NAME,SIZE,TYPE,FSTYPE",
                device,
            ],
            universal_newlines=True,
        )
    )
    if type(out) is not dict:
        raise TypeError(
            "Unexpected return type from lsblk, "
            + f"expected dict, got {type(out)}"
        )
    # the return value should be a dict with "blockdevices" as the only key
    # index into it and we get a list of block devices
    block_devices: "list[BlockDevice]" = []
    for raw_json in out["blockdevices"]:
        block_device = BlockDevice(
            name=raw_json["name"],
            size=int(raw_json["size"]),
            type=raw_json["type"],
            fstype=raw_json["fstype"],
        )
        # skip the "raw" disks, LUKS partitions, and partitions with no
        # filesystem (fstype is None means it's not formatted)

        if block_device.type not in ACCEPTED_DEVICE_TYPES:
            print(
                f"Skipping {block_device.name}",
                f"because it's of type '{block_device.type}',",
                f"but we need {ACCEPTED_DEVICE_TYPES}",
                file=sys.stderr,
            )
            continue
        if block_device.fstype not in get_mountable_fstypes():
            print(
                f"Skipping {block_device.name}",
                f"because it has unmountable fstype '{block_device.fstype}',",
                f"but we need {get_mountable_fstypes()}",
            )
            continue

        block_devices.append(block_device)

    if not block_devices:
        raise SystemExit(
            f"ERROR: No suitable partitions found on device {device}"
        )
    block_devices.sort(key=lambda bd: bd.size)
    # it should be always under /dev
    return Path("/dev") / block_devices[-1].name


def mount(source: Path, target: Path):
    print(f"+ mount {source} {target}", flush=True)
    sp.check_call(["mount", source, target])


def unmount(target: Path):
    print(f"+ umount {target}", flush=True)
    sp.check_call(["umount", target])


def memory() -> float:
    return psutil.virtual_memory().total / (1024 * 1024)


def free_space(test_dir: Path) -> float:
    du = psutil.disk_usage(str(test_dir))
    return du.free / (1024 * 1024)


def devmapper_name(udev_name: str) -> "str | None":
    sys_block_device = Path("/sys/block") / udev_name
    if (sys_block_device / "dm").is_dir():
        return (sys_block_device / "dm" / "name").read_text().strip()


def run_bonnie(test_dir: Path, user: str = "root"):
    # Set a maximum size on the amount of RAM, this has the effect of keeping
    # the amount of data written during tests lower than default. This keeps
    # duration of tests at something reasonable
    force_mem_mb = min(8000, memory())
    # When running on disks with small drives (SSD/flash) we need to do
    # some tweaking. Bonnie uses 2x RAM by default to write data. If that's
    # more than available disk space, the test will fail inappropriately.
    free = free_space(test_dir)
    print(f"{free}MB of free space available")
    if (force_mem_mb * 2) > free:
        force_mem_mb = round(free / 4)
    print(f"Forcing memory setting to {force_mem_mb}MB")
    cmd = ["bonnie++", "-d", test_dir, "-u", user, "-r", str(force_mem_mb)]
    print("+", " ".join(map(str, cmd)), flush=True)
    sp.check_call(cmd)


def devmapper_test(udev_name: str):
    print(f"Identified {udev_name} as a devmapper device...")
    device = Path("/dev") / udev_name
    mount_dir = mountpoint(device)
    if mount_dir:
        print(f"{device} already mounted at {mount_dir}")
    else:
        dm_name = devmapper_name(udev_name)
        if dm_name:
            dm_device = Path("/dev/mapper") / dm_name
            if os.path.exists(dm_device):
                mount_dir = mountpoint(dm_device)
                if mount_dir:
                    print(f"{dm_device} already mounted at {mount_dir}")
    with ExitStack() as stack:
        if mount_dir is None:
            mount_dir = Path(tempfile.mkdtemp())
            stack.callback(os.rmdir, mount_dir)
            mount(device, mount_dir)
            print(f"Performed mount of {device} at {mount_dir}")
            stack.callback(unmount, mount_dir)
        run_bonnie(mount_dir)


def disk_test(udev_name: str):
    print(f"Identified {udev_name} as a disk...")
    device = Path("/dev") / udev_name
    partition_to_test = find_largest_partition(device)
    print(f"Test will be run on the largest partition {partition_to_test}")

    mount_dir = mountpoint(partition_to_test)
    if mount_dir:
        print(f"{partition_to_test} already mounted at {mount_dir}")

    with ExitStack() as stack:
        if mount_dir is None:
            mount_dir = Path(tempfile.mkdtemp())
            stack.callback(os.rmdir, mount_dir)
            mount(partition_to_test, mount_dir)
            print(f"Performed mount {partition_to_test} at {mount_dir}")
            stack.callback(unmount, mount_dir)
        run_bonnie(mount_dir)


def parse_args() -> str:
    p = ArgumentParser()
    p.add_argument("udev_disk_name", type=str)
    return p.parse_args().udev_disk_name


def main():
    udev_name = parse_args()

    if os.getuid() != 0:
        raise SystemExit("You must run this program as root")

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
