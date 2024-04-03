#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright (C) 2010-2013 by Cloud Computing Center for Mobile Applications
# Industrial Technology Research Institute
# Copyright 2024 Canonical Ltd.
#
# Authors:
#   Nelson Chu <Nelson.Chu@itri.org.tw>
#   Jeff Lane <jeff@ubuntu.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
"""
disk_resource creates a resource per disk from the output of lsblk.
- name: column KNAME, internal kernel name
- path: column PATH, path to the device node
- model: column MODEL, model identifier
- size: column SIZE, size of the disk in bytes
- rotational: column ROTA, True for rotational drives like hard disks
"""

import json
from subprocess import check_output, CalledProcessError


def get_blockdevices_info() -> dict:
    try:
        lsblk_out_text = check_output(
            [
                "lsblk",
                "--json",
                "--bytes",
                "--ascii",
                "--noheadings",
                "--output",
                "KNAME,PATH,TYPE,SIZE,MODEL,ROTA,MOUNTPOINT",
            ],
            universal_newlines=True,
        )
    except CalledProcessError as e:
        raise SystemExit(str(e))
    lsblk_out = json.loads(lsblk_out_text)
    return lsblk_out["blockdevices"]


def get_relevant_block_devices(block_devices: list) -> list:
    """
    Filters out every block device that we don't usually consider a disk
    like, for example, loopback devices
    """

    def include(block_device):
        if block_device["type"] not in ("disk", "crypt"):
            return False
        is_mmcblk = block_device["kname"].startswith("mmcblk")
        whitelisted_mountpoints = {
            "/",
            "/writable",
            "/hostfs",
            "/ubuntu-seed",
            "/ubuntu-boot",
            "/ubuntu-save",
            "/data",
            "/boot",
        }
        if is_mmcblk and block_device["mountpoint"] in whitelisted_mountpoints:
            return False
        if "snapd/save" in (block_device.get("mountpoint") or ""):
            return False
        return True

    return filter(include, block_devices)


def print_as_resource(block_device):
    model = block_device.get("model", "Unknown")
    print("name:", block_device["kname"])
    print("path:", block_device["path"])
    print("model:", model)
    print("size:", block_device["size"])
    print("rotational:", block_device["rota"])
    print()


def main():
    """
    Uses lsblk to gather information about disks seen by the OS.
    """
    block_devices = get_blockdevices_info()
    relevant_block_devices = get_relevant_block_devices(block_devices)
    for block_device in relevant_block_devices:
        print_as_resource(block_device)


if __name__ == "__main__":
    main()
