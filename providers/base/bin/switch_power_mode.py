#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Bin Li <bin.li@canonical.com>

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
    profile = "power-saver" if profile == "low-power" else profile
    try:
        subprocess.check_call(["powerprofilesctl", "set", profile])
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Failed to set power mode to {profile}.") from e


def main():
    """main function to switch the power mode."""
    sysfs_root = Path("/sys/firmware/acpi/")
    choices_path = sysfs_root / "platform_profile_choices"
    profile_path = sysfs_root / "platform_profile"

    # use a context manager to ensure the original power mode is restored
    with contextlib.ExitStack() as stack:
        # Read the current power mode from /sys/firmware/acpi/platform_profile
        old_profile = get_sysfs_content(profile_path)
        stack.callback(set_power_profile, old_profile)

        choices = get_sysfs_content(choices_path).split()

        print("Power mode choices: {}".format(choices))
        for choice in choices:
            set_power_profile(choice)
            if get_sysfs_content(profile_path) == choice:
                print("Switch to {} successfully.".format(choice))
            else:
                raise SystemExit("Failed to switch power mode to {}".format(choice))


if __name__ == "__main__":
    main()
