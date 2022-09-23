#!/usr/bin/env python3

"""
Script to test that the system PXE-booted, if run in EFI mode

Copyright (c) 2016 Canonical Ltd.

Authors
   Rod Smith <rod.smith@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

The purpose of this script is to identify whether an EFI-based
system booted from the network (test passes) or from a local disk
(test fails).

Usage:
   efi-pxeboot.py
"""

import os
import shlex
import shutil
import sys

from subprocess import Popen, PIPE


def discover_data():
    """Extract boot entry and boot order information.

    :returns:
        boot_entries, boot_order, boot_current
    """
    command = "efibootmgr -v"
    bootinfo_bytes = (Popen(shlex.split(command), stdout=PIPE)
                      .communicate()[0])
    bootinfo = (bootinfo_bytes.decode(encoding="utf-8", errors="ignore")
                .splitlines())
    boot_entries = {}
    boot_order = []
    boot_current = ""
    if len(bootinfo) > 1:
        for s in bootinfo:
            if "BootOrder" in s:
                try:
                    boot_order = s.split(":")[1].replace(" ", "").split(",")
                except IndexError:
                    pass
            elif "BootCurrent" in s:
                try:
                    boot_current = s.split(":")[1].strip()
                except IndexError:
                    pass
            else:
                # On Boot#### lines, #### is characters 4-8....
                hex_value = s[4:8]
                # ....and the description starts at character 10
                name = s[10:]
                try:
                    # In normal efibootmgr output, only Boot#### entries
                    # have characters 4-8 that can be interpreted as
                    # hex values, so this will harmlessly error out on all
                    # but Boot#### entries....
                    int(hex_value, 16)
                    boot_entries[hex_value] = name
                except ValueError:
                    pass
    return boot_entries, boot_order, boot_current


def is_pxe_booted(boot_entries, boot_order, boot_current):
    retval = 0
    desc = boot_entries[boot_current]
    print("The current boot item is {}".format(boot_current))
    print("The first BootOrder item is {}".format(boot_order[0]))
    print("The description of Boot{} is '{}'".format(boot_current, desc))
    if boot_current != boot_order[0]:
        # If the BootCurrent entry isn't the same as the first of the
        # BootOrder entries, then something is causing the first boot entry
        # to fail or be bypassed. This could be a Secure Boot failure, manual
        # intervention, a bad boot entry, etc. This is not necessarily a
        # problem, but warn of it anyhow....
        desc2 = boot_entries[boot_order[0]]
        print("The description of Boot{} is '{}'".format(boot_order[0], desc2))
        print("WARNING: The system is booted using Boot{}, but the first".
              format(boot_current))
        print("boot item is Boot{}!".format(boot_order[0]))
    if "Network" in desc or "PXE" in desc or "NIC" in desc \
            or "Ethernet" in desc or "IP4" in desc or "IP6" in desc:
        # These strings are present in network-boot descriptions.
        print("The system seems to have PXE-booted; all OK.")
    elif "ubuntu" in desc or "grub" in desc or "shim" in desc or "rEFInd" \
            or "refind_" in desc:
        # This string indicates a boot directly from the normal Ubuntu GRUB
        # or rEFInd installation on the hard disk.
        print("FAIL: The system has booted directly from the hard disk!")
        retval = 1
    elif "SATA" in desc or "Sata" in desc or "Hard Drive" in desc:
        # These strings indicate booting with a "generic" disk entry (one
        # that uses the fallback filename, EFI/BOOT/bootx64.efi or similar).
        print("The system seems to have booted from a disk with the fallback "
              "boot loader!")
        retval = 1
    else:
        # Probably a rare description. Call it an error so we can flag it and
        # improve this script.
        print("Unable to identify boot path.")
        retval = 1
    return retval


def main():
    """Check to see if the system PXE-booted."""

    if shutil.which("efibootmgr") is None:
        print("The efibootmgr utility is not installed; exiting!")
        return(4)
    if not os.geteuid() == 0:
        print("This program must be run as root (or via sudo); exiting!")
        return(4)

    retval = 0
    boot_entries, boot_order, boot_current = discover_data()
    if boot_entries == {}:
        print("No EFI boot entries are available. This may indicate a "
              "firmware problem.")
        retval = 2
    if boot_order == []:
        print("The EFI BootOrder variable is not available. This may "
              "indicate a firmware")
        print("problem.")
        retval = 3
    if boot_current == "":
        print("FAIL: The EFI BootCurrent variable is missing. This may "
              "indicate a firmware")
        print("problem.")
        retval = 4
    if (retval == 0):
        retval = is_pxe_booted(boot_entries, boot_order, boot_current)
    return(retval)


if __name__ == '__main__':
    sys.exit(main())
