#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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
#

"""Modules providing a function running os or sys commands."""
import sys
import os


def main():
    """Dump the power mode."""
    sysfs_root = "/sys/firmware/acpi/"
    if not os.path.isdir(sysfs_root):
        return 1

    profile_filename = os.path.join(sysfs_root, "platform_profile")
    if (not os.path.isfile(profile_filename) or
            not os.access(profile_filename, os.R_OK)):
        return 1

    with open(profile_filename, "rt", encoding="utf-8") as stream:
        profile = stream.read().strip().split()
        if len(profile) < 1:
            return 1
        else:
            print(profile[0])
            # uncomment the following line to do local testing
            #os.system(f"powerprofilesctl set power-saver")
            return 0


if __name__ == "__main__":
    sys.exit(main())
