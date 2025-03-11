#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Authors:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
import argparse
import os
import shutil
from packaging import version

from checkbox_support.snap_utils.asserts import decode, model_to_resource

from checkbox_support.snap_utils.snapd import Snapd


def get_kernel_config_path():
    """Retrieve the path to the kernel configuration file."""
    kernel_version = os.uname().release
    path_list = []
    for model in decode(Snapd().get_assertions("model")):
        resource = model_to_resource(model)
        if resource.get("kernel"):
            config_path = "/snap/{}/current/config-{}".format(
                resource["kernel"], kernel_version
            )
            path_list.append(config_path)

    # Check for the kernel configuration in the host filesystem and in the
    # boot partition
    path_list.extend(
        [
            "/var/lib/snapd/hostfs/boot/config-{}".format(kernel_version),
            "/boot/config-{}".format(kernel_version),
        ]
    )

    for path in path_list:
        if os.path.exists(path):
            return path
    raise SystemExit("Kernel configuration not found.")


def get_configuration(output=None):
    """Retrieve and optionally save the kernel configuration."""
    kernel_config_path = get_kernel_config_path()
    if output:
        shutil.copy2(kernel_config_path, output)
    else:
        with open(kernel_config_path) as config:
            print(config.read())


def check_flag(flag, min_version):
    """Check if a specific flag is true in the kernel configuration starting
    from a specific version."""

    version_parts = os.uname().release.split("-")
    kernel_version = "-".join(version_parts[:2])
    if min_version and version.parse(kernel_version) < version.parse(
        min_version
    ):
        print(
            "Kernel version is {}.".format(kernel_version),
            "Versions lower than {} don't require ".format(min_version),
            "the flag {} to be set.".format(flag),
        )
        return

    kernel_config_path = get_kernel_config_path()
    with open(kernel_config_path) as config:
        # Check the header and ignore arm architecture configurations
        lines = config.readlines()

        # Look for the flag in the configuration
        for line in lines:
            line = line.strip()
            if line.startswith("#"):
                continue  # Ignore commented lines
            if "{}=y".format(flag) in line:
                print("Flag {} is present and set to 'y'.".format(flag))
                return

    raise SystemExit("Flag {} not found in the kernel config.".format(flag))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", "-o", help="Output file to store the kernel configuration"
    )
    parser.add_argument(
        "--config-flag",
        "-c",
        help="Check if a specific flag is present in the configuration",
    )
    parser.add_argument(
        "--min-version",
        "-m",
        help="Minimum kernel version required to check the flag",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.config_flag:
        check_flag(args.config_flag, args.min_version)
    else:
        get_configuration(args.output)


if __name__ == "__main__":
    main()
