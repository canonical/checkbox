#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Bin Li <bin.li@canonical.com>

""" Switching the power mode to check if the power mode can be switched. """
from pathlib import Path
import sys
import subprocess


def main():
    """ main function to switch the power mode. """
    sysfs_root = Path("/sys/firmware/acpi/")
    choices_path = sysfs_root / "platform_profile_choices"
    profile_path = sysfs_root / "platform_profile"

    return_value = 0

    try:
        result = subprocess.check_output(["powerprofilesctl", "get"], text=True)
        old_profile = result.strip().split()[0]
    except subprocess.CalledProcessError as err:
        raise SystemExit("Failed to get the current power mode.".format(err))

    # Read the power mode from /sys/firmware/acpi/platform_profile_choices
    with open(choices_path, "rt", encoding="utf-8") as stream:
        choices = stream.read().strip().split()
        if not choices:
            raise SystemExit("No power mode to switch.")

    print('Power mode choices: {}'.format(choices))
    # Switch the power mode with powerprofilesctl
    for choice in choices:
        # Convert the power mode, e.g. low-power = power-saver,
        # balanced and performance keep the same.
        if choice == "low-power":
            value = "power-saver"
        else:
            value = choice

        subprocess.check_call(["powerprofilesctl", "set", value])

        with open(profile_path, "rt", encoding="utf-8") as stream:
            current_profile = stream.read().strip().split()
        if current_profile[0] == choice:
            print("Switch to {} successfully.".format(value))
        else:
            print("Failed to switch to {}.".format(value))
            return_value = 1

    # Switch back to the original power mode
    subprocess.check_call(["powerprofilesctl", "set", old_profile])

    sys.exit(return_value)


if __name__ == "__main__":
    main()
