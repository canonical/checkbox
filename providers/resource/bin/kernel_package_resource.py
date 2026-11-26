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


from checkbox_support.snap_utils.system import (
    add_hostfs_prefix,
    get_kernel_snap,
    on_ubuntucore,
)
from checkbox_support.helpers.release_info import get_release_info
import subprocess
import os


def get_kernel_package_info():

    # If we are on Ubuntu Core, just call the get_kernel_snap function
    if on_ubuntucore():
        return get_kernel_snap(), "snap"

    # If we are not on Ubuntu Core, we need to check the kernel package
    # installed on the system.

    kernel_version = os.uname().release
    dpkg_admin_dir = add_hostfs_prefix("/var/lib/dpkg")
    try:
        package_info = subprocess.check_output(
            [
                "dpkg-query",
                "--admindir",
                dpkg_admin_dir,
                "-W",
                "-f=${db:Status-Status}\t${source:Package}\n",
                f"linux-modules-{kernel_version}",
            ],
            universal_newlines=True,
        )
    except subprocess.CalledProcessError as exc:
        if exc.returncode != 1:
            raise
        # A missing dpkg database also looks like a missing package.
        with open(os.path.join(dpkg_admin_dir, "status")):
            pass
        return None, "deb"
    except FileNotFoundError as exc:
        raise SystemExit("Unable to find dpkg-query.") from exc
    for line in package_info.splitlines():
        status, separator, source_package = line.partition("\t")
        source_package = source_package.strip()
        if separator and status == "installed" and source_package:
            return source_package, "deb"
    return None, "deb"


def main():
    release = get_release_info().get("release")
    if not release:
        raise SystemExit("Unable to get release information.")

    kernel_package, kernel_type = get_kernel_package_info()
    if not kernel_package:
        raise SystemExit("No kernel package found.")

    print(f"name: {kernel_package}")
    print(f"type: {kernel_type}")
    print(f"release: {release}")


if __name__ == "__main__":
    main()
