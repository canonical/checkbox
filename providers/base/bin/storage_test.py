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
import tempfile
from argparse import ArgumentParser
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import psutil


class BlockDevice(NamedTuple):
    # warning: these types are not enforced without explicit checks at runtime
    name: str  # nvme0n1p3, dm_crypt-0
    size: int
    type: str  # lvm, part, crypt
    fstype: "str  | None"  # ext4, vfat, crypto_LUKS


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
    blk_devs: "list[BlockDevice]" = []
    for raw_json in out["blockdevices"]:
        blk_devs.append(
            BlockDevice(
                name=raw_json["name"],
                size=raw_json["size"],
                type=raw_json["type"],
                fstype=raw_json["fstype"],
            )
        )
    # skip the "raw" disks and LUKS partition
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
    # it should be always under /dev
    return Path("/dev") / blk_devs[-1].name


def mount(source: Path, target: Path):
    print(f"+ mount {source} {target}", flush=True)
    sp.check_call(["mount", source, target])


def unmount(target: Path):
    print(f"+ unmount {target}", flush=True)
    sp.check_call(["unmount", target])


def memory() -> float:
    return psutil.virtual_memory().total / (1024 * 1024)


def free_space(test_dir: Path) -> float:
    du = psutil.disk_usage(str(test_dir))
    return du.free / (1024 * 1024)


def devmapper_name(udev_name: str) -> "str | None":
    sys_block_device = Path("/sys/block") / udev_name
    if (sys_block_device / "dm").is_dir():
        return (sys_block_device / "dm" / "name").read_text()


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
        force_mem_mb = free / 4
    print(f"Forcing memory setting to {force_mem_mb}MB")
    cmd = f"bonnie++ -d {test_dir} -u {user} -r {force_mem_mb}"
    print("+", cmd, flush=True)
    sp.check_call(cmd, shell=True)


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
    part_to_test = find_largest_partition(device)
    print(f"Test will be run on partition {part_to_test}")

    mount_dir = mountpoint(part_to_test)
    if mount_dir:
        print(f"{part_to_test} already mounted at {mount_dir}")

    with ExitStack() as stack:
        if mount_dir is None:
            mount_dir = Path(tempfile.mkdtemp())
            stack.callback(os.rmdir, mount_dir)
            mount(part_to_test, mount_dir)
            print(f"Performed mount {part_to_test} at {mount_dir}")
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
