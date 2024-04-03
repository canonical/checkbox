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

# pylint: disable=consider-using-f-string

""" Switching the power mode to check if the power mode can be switched. """
from pathlib import Path
import subprocess
import contextlib


def get_sysfs_content(path):
    """
    Reads the content of a sysfs file.
    Args:
        path (pathlib.Path): Path to the sysfs file.
    Raises:
        SystemExit: If the file could not be read.
    """
    with open(path, "rt", encoding="utf-8") as stream:
        content = stream.read().strip()
    if not content:
        raise SystemExit("Failed to read sysfs file: {}".format(path))
    return content


def set_power_profile(profile):
    """
    Sets the power profile to the specified value.
    Args:
        profile (str): The power profile to set (e.g., "power-saver").
    Raises:
        SystemExit: If the power profile could not be set.
    """
    # In sys file the modes are low-power, balanced, or performance
    # but powerprofilesctl only accepts power-saver, balanced or performance
    profile = "power-saver" if profile == "low-power" else profile
    try:
        subprocess.check_call(["powerprofilesctl", "set", profile])
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            "Failed to set power mode to {}.".format(profile)
        ) from e


@contextlib.contextmanager
def preserve_power_profile():
    """
    Rolls back the power profile to the original before calling
    """
    sysfs_root = Path("/sys/firmware/acpi/")
    profile_path = sysfs_root / "platform_profile"
    old_profile = get_sysfs_content(profile_path)
    try:
        yield
    finally:
        set_power_profile(old_profile)


def main():
    """main function to switch the power mode."""
    sysfs_root = Path("/sys/firmware/acpi/")
    choices_path = sysfs_root / "platform_profile_choices"
    profile_path = sysfs_root / "platform_profile"

    # use a context manager to ensure the original power mode is restored
    with preserve_power_profile():

        choices = get_sysfs_content(choices_path).split()

        print("Power mode choices: {}".format(choices))
        for choice in choices:
            set_power_profile(choice)
            if get_sysfs_content(profile_path) == choice:
                print("Switch to {} successfully.".format(choice))
            else:
                raise SystemExit(
                    "ERROR: Failed to switch power mode to {}".format(choice)
                )


if __name__ == "__main__":
    main()
