#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
#    Authors: Bin Li <bin.li@canonical.com>
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

from pathlib import Path


def check_platform_profiles():
    """check platform_profiles and print supported or unsupported."""
    supported = False

    sysfs_root = Path("/sys/firmware/acpi/")
    choices_path = sysfs_root / "platform_profile_choices"
    profile_path = sysfs_root / "platform_profile"

    supported = (
        sysfs_root.exists() and choices_path.exists() and profile_path.exists()
    )

    print("supported: {}".format(supported))


def main():
    """main function."""
    check_platform_profiles()


if __name__ == "__main__":
    main()
