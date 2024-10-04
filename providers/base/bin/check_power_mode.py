#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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
#

"""Check current power mode."""
from pathlib import Path
from switch_power_mode import get_sysfs_content


def main():
    """main function to read the power mode."""
    sysfs_root = Path("/sys/firmware/acpi/")
    profile_path = sysfs_root / "platform_profile"

    profile = get_sysfs_content(profile_path)
    print(profile)
    # uncomment the following lines to set another mode for testing
    # from switch_power_mode import set_power_profile
    # set_power_profile("power-saver")


if __name__ == "__main__":
    main()
