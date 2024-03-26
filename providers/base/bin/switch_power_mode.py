#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Bin Li <bin.li@canonical.com>

"""Modules providing a function running os or sys commands."""
import os
import sys


def main():
    """Switching the power mode to check if the power mode can be switched."""
    sysfs_root = "/sys/firmware/acpi/"
    if not os.path.isdir(sysfs_root):
        return
    choices_filename = os.path.join(sysfs_root, "platform_profile_choices")
    if (not os.path.isfile(choices_filename) or
            not os.access(choices_filename, os.R_OK)):
        return
    profile_filename = os.path.join(sysfs_root, "platform_profile")
    if (not os.path.isfile(profile_filename) or
            not os.access(profile_filename, os.R_OK)):
        return

    return_value = 0

    # Get the current power mode in quiet mode.
    old_profile = os.popen("powerprofilesctl get").read().strip().split()[0]

    # Read the power mode from /sys/firmware/acpi/platform_profile_choices
    with open(choices_filename, "rt", encoding="utf-8") as stream:
        choices = stream.read().strip().split()
        if len(choices) < 1:
            print("No power mode to switch.")
            return
    print(f'Power mode choices: {choices}')
    # Switch the power mode with powerprofilesctl
    for choice in choices:
        # Convert the power mode, e.g. low-power = power-saver,
        # balanced and performance keep the same.
        if choice == "low-power":
            value = "power-saver"
        else:
            value = choice

        os.system(f"powerprofilesctl set {value}")

        os.system("sleep 2")

        with open(profile_filename, "rt", encoding="utf-8") as stream:
            current_profile = stream.read().strip().split()
        if current_profile[0] == choice:
            print(f"Switch to {value} successfully.")
        else:
            print(f"Failed to switch to {value}.")
            return_value = 1

    # Switch back to the original power mode
    os.system(f"powerprofilesctl set {old_profile}")

    sys.exit(return_value)


if __name__ == "__main__":
    main()
