#!/usr/bin/env python3
# Copyright 2018 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

"""Test that Full Disk Encryption is in use.

$ fde_tests.py
Canonical has a reference implementation of full disk encryption for IoT
devices. With no arguments passed this test checks this implementation is in
operation on the device under test.

$ fde_tests.py desktop
Checks if the system appears to be using full disk encryption as configured by
the desktop installer.
"""

import os
import subprocess as sp
import sys

from checkbox_support.snap_utils.system import get_series


def main():
    on_desktop = len(sys.argv) > 1 and sys.argv[1] == "desktop"

    # discover the underlying mount point for the encrypted part
    if on_desktop:
        cmd = "findmnt {} -n -o SOURCE".format("/")
    else:
        if int(get_series()) >= 20:
            cmd = "findfs LABEL=ubuntu-data"
        else:
            cmd = "findfs LABEL=writable"
    print(f"+ {cmd}")
    try:
        source = (
            sp.check_output(cmd, shell=True)
            .decode(sys.stdout.encoding)
            .strip()
        )
    except sp.CalledProcessError:
        raise SystemExit(
            "ERROR: could not find mountpoint for the encrypted partition"
        )
    print(source, "\n")

    # resolve the source to an actual device node
    print(f"+ realpath {source}")
    device = os.path.realpath(source)
    print(device, "\n")

    # work upwards through the tree of devices until we find the one that has
    # the type 'crypt'
    kname = os.path.basename(device)
    while True:
        cmd = f'lsblk -r -n -i -o KNAME,TYPE,PKNAME | grep "^{kname}"'
        print(f"+ {cmd}")
        try:
            lsblk = (
                sp.check_output(cmd, shell=True)
                .decode(sys.stdout.encoding)
                .strip()
            )
        except sp.CalledProcessError:
            raise SystemExit("ERROR: lsblk call failed")
        _, devtype, parent = lsblk.split(maxsplit=2)
        print(devtype, "\n")
        if devtype == "crypt":
            # found the device
            break
        if devtype == "disk":
            # reached the physical device, end the search
            raise SystemExit(
                'ERROR: could not find a block device of type "crypt"'
            )
        kname = parent

    # the presence of device with type 'crypt' is probably confirmation enough
    # but to be really sure lets check to see it is found by cryptsetup

    # first we need to know its mapper name
    cmd = f'dmsetup info /dev/{kname} | grep "^Name:"'
    print(f"+ {cmd}")
    try:
        mapper_name = (
            sp.check_output(cmd, shell=True)
            .decode(sys.stdout.encoding)
            .strip()
            .split()[-1]
        )
    except sp.CalledProcessError:
        raise SystemExit(f"ERROR: dmsetup info on device {kname} failed")
    print(mapper_name, "\n")

    # then query the info in cryptsetup
    cmd = f"cryptsetup status {mapper_name}"
    print(f"+ {cmd}")
    try:
        cryptinfo = (
            sp.check_output(cmd, shell=True)
            .decode(sys.stdout.encoding)
            .strip()
        )
    except sp.CalledProcessError:
        raise SystemExit("ERROR: cryptsetup check failed")
    print(cryptinfo)
    print("\nFull Disk Encryption is operational on this device")


if __name__ == "__main__":
    main()
