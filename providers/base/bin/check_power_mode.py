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

"""Check current power mode."""
from pathlib import Path
from switch_power_mode import get_sysfs_content


def main():
    """main function to read the power mode."""
    sysfs_root = Path("/sys/firmware/acpi/")
    profile_path = sysfs_root / "platform_profile"

    profile = get_sysfs_content(profile_path).split()
    print(profile[0])
    # uncomment the following line to change another mode
    # os.system(f"powerprofilesctl set power-saver")


if __name__ == "__main__":
    main()
