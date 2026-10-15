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

ACCEPTED_DEVICE_TYPES = (
    "part",
    "raid0",
    "raid1",
    "raid4",
    "raid5",
    "raid6",
    "raid10",
    "linear",
    # an unlocked LUKS volume, and LVM volumes (e.g. the default Ubuntu
    # encrypted install: part(crypto_LUKS) -> crypt(LVM2_member) -> lvm)
    # only show up in lsblk once they are opened, so they are testable
    "crypt",
    "lvm",
)


class BlockDevice(NamedTuple):
    # warning: these types are not enforced without explicit checks at runtime
    name: str  # name in lsblk, nvme0n1p3, dm_crypt-0
    kname: str  # kernel internal name, nvme0n1p3, dm-0
    size: int  # in bytes
    type: str  # lvm, part, crypt
    fstype: "str | None"  # ext4, vfat, crypto_LUKS


# lsblk FSTYPE values that are not writable filesystems.
# None means lsblk found no filesystem signature.
# squashfs and iso9660 are mountable but read-only, so bonnie++ would fail
REJECTED_FSTYPES = (
    None,
    "swap",
    "crypto_LUKS",
    "LVM2_member",
    "linux_raid_member",
    "zfs_member",
    "squashfs",
    "iso9660",
)


# file size of the per-char bonnie++ run, -r 0 disables the 2x RAM check
PER_CHAR_SIZE_MB = 64

# bonnie++ writes the bulk IO test data to a single file, so it can't be
# larger than the max file size of the filesystem, FAT is limited to 4GiB - 1
FS_MAX_FILE_SIZE_MB = {"vfat": 4095, "msdos": 4095}


def mountpoint(device: Path) -> "Path | None":
    for part in psutil.disk_partitions():
        if Path(part.device).resolve() == device.resolve():
            return Path(part.mountpoint)
    return None


def get_fs_type(mount_dir: Path) -> "str | None":
    for part in psutil.disk_partitions(all=True):
        if Path(part.mountpoint) == mount_dir:
            return part.fstype
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
                "NAME,KNAME,SIZE,TYPE,FSTYPE",
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
            kname=raw_json["kname"],
            size=int(raw_json["size"]),
            type=raw_json["type"],
            fstype=raw_json["fstype"],
        )
        # skip the "raw" disks, locked LUKS partitions, and partitions with
        # no filesystem (fstype is None means it's not formatted)

        if block_device.type not in ACCEPTED_DEVICE_TYPES:
            print(
                f"Skipping {block_device.name}",
                f"because it's of type '{block_device.type}',",
                f"but we need {ACCEPTED_DEVICE_TYPES}",
                file=sys.stderr,
            )
            continue
        if block_device.fstype in REJECTED_FSTYPES:
            print(
                f"Skipping {block_device.name}",
                f"because its fstype '{block_device.fstype}'",
                "is not a writable filesystem",
                file=sys.stderr,
            )
            continue

        block_devices.append(block_device)

    if not block_devices:
        raise SystemExit(
            f"ERROR: No suitable partitions found on device {device}"
        )
    block_devices.sort(key=lambda bd: bd.size, reverse=True)
    # NAME of dm devices (e.g. ubuntu--vg-ubuntu--lv) is not under /dev,
    # but KNAME (e.g. dm-0) always is
    return Path("/dev") / block_devices[0].kname


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
    force_mem_mb = int(min(8000, memory()))
    # When running on disks with small drives (SSD/flash) we need to do
    # some tweaking. Bonnie uses 2x RAM by default to write data. If that's
    # more than available disk space, the test will fail inappropriately.
    free = free_space(test_dir)
    print(f"{free}MB of free space available")
    if (force_mem_mb * 2) > free:
        force_mem_mb = round(free / 4)

    fs_type = get_fs_type(test_dir)
    if fs_type:
        max_file_size_mb = FS_MAX_FILE_SIZE_MB.get(fs_type)
        if max_file_size_mb and force_mem_mb * 2 > max_file_size_mb:
            print(
                "Limiting file size to the",
                f"{max_file_size_mb}MB limit of {fs_type}",
            )
            force_mem_mb = max_file_size_mb // 2

    print(f"Forcing memory setting to {force_mem_mb}MB")

    base_cmd = ["bonnie++", "-d", test_dir, "-u", user]
    bulk_cmd = base_cmd + [
        "-r",
        str(force_mem_mb),
        # set the size explicitly, otherwise bonnie++ rounds 2x RAM up to
        # the nearest GiB, which can exceed the fs file size limit
        "-s",
        str(force_mem_mb * 2),
        # bypass the page cache, O_DIRECT
        # see `man bonnie++`
        "-D",
        # skip the per-char tests, O_DIRECT requires block aligned writes
        # so writing a byte at a time always fails with -D
        "-f",
    ]
    # O_DIRECT can't be used for per-char IO, so run those tests separately
    # with a small file and without the file creation tests
    per_char_cmd = base_cmd + ["-r", "0", "-s", str(PER_CHAR_SIZE_MB)]
    per_char_cmd += ["-n", "0"]

    print(" Bonnie++ bulk IO tests ".center(80, "="))
    print("+", " ".join(map(str, bulk_cmd)), flush=True)
    sp.check_call(bulk_cmd)

    print(" Bonnie++ per-char IO tests ".center(80, "="))
    print("+", " ".join(map(str, bulk_cmd)), flush=True)
    sp.check_call(per_char_cmd)


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
