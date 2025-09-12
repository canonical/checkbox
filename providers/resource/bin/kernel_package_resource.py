#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
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


from checkbox_support.snap_utils.system import on_ubuntucore, get_kernel_snap
from checkbox_support.helpers.release_info import get_release_info
import subprocess
import os


def get_kernel_package_info():

    # If we are on Ubuntu Core, just call the get_kernel_snap function
    if on_ubuntucore():
        return get_kernel_snap(), "snap"

    # If we are not on Ubuntu Core, we need to check the kernel package
    # installed on the system.

    # Get the kernel version
    kernel_version = os.uname().release
    linux_modules_info = subprocess.check_output(
        ["apt-cache", "show", "linux-modules-{}".format(kernel_version)],
        universal_newlines=True,
        stderr=subprocess.DEVNULL,
    )
    for line in linux_modules_info.splitlines():
        if line.startswith("Source:"):
            kernel_package = line.split(":")[1].strip()
            return kernel_package, "deb"


def main():
    release = get_release_info().get("release")
    if not release:
        raise SystemExit("Unable to get release information.")

    kernel_package, kernel_type = get_kernel_package_info()
    if not kernel_package:
        raise SystemExit("No kernel package found.")

    print("name: {}".format(kernel_package))
    print("type: {}".format(kernel_type))
    print("release: {}".format(release))


if __name__ == "__main__":
    main()
