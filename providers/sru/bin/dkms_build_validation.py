#!/usr/bin/env python3
#
# Copyright 2017-2024 Canonical Ltd.
# Written by:
#   Taihsiang Ho (tai271828) <taihsiang.ho@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import Counter
from packaging import version
import re
import subprocess
import sys
import textwrap


def run_command(command):
    """Run a shell command and return its output"""
    try:
        result = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            shell=True,
            universal_newlines=True,
        )
        return result.strip()
    except subprocess.CalledProcessError as e:
        raise Exception(
            "Command '{0}' failed with error: {1}".format(command, e.output)
        )


def parse_version(ver):
    # Attempt to split the version into its numeric and suffix components
    match = re.match(r"(\d+\.\d+\.\d+-\d+)", ver)
    if match:
        parsed_version = version.parse(match.group(1))
    else:
        raise ValueError("Invalid version string: {0}".format(ver))

    return parsed_version


def main():
    ubuntu_release = run_command("lsb_release -r | cut -d ':' -f 2 | xargs")
    dkms_status = run_command("dkms status")

    kernel_info = []
    for line in dkms_status.splitlines():
        # split the line by the : and store each one in a set
        details, status = line.split(": ")

        if version.parse(ubuntu_release) >= version.parse("22.04"):
            kernel_ver = details.split(", ")[1]
        else:
            kernel_ver = details.split(", ")[2]
        kernel_info.append({"version": kernel_ver, "status": status})

    sorted_kernel_info = sorted(
        kernel_info, key=lambda x: parse_version(x["version"])
    )

    kernel_ver_max = sorted_kernel_info[-1]["version"]
    kernel_ver_min = sorted_kernel_info[0]["version"]

    # kernel_ver_max should be the same as kernel_ver_current
    kernel_ver_current = run_command("uname -r")
    if kernel_ver_max != kernel_ver_current:
        msg = textwrap.dedent(
            """
            Current kernel version does not match the latest built DKMS module.
            Your running kernel: {kernel_ver_current}
            Latest DKMS module built on kernel: {kernel_ver_max}
            Maybe the target DKMS was not built,
            or you are not running the latest available kernel.
            """.format(
                kernel_ver_current=kernel_ver_current,
                kernel_ver_max=kernel_ver_max,
            )
        )
        print(msg)
        print("=== DKMS status ===\n{0}".format(dkms_status))
        return 1

    # Count the occurernces of the latest and the oldest kernel version and
    # compare the number of DKMS modules for min and max kernel versions
    version_count = Counter([item["version"] for item in sorted_kernel_info])
    number_dkms_min = version_count[kernel_ver_min]
    number_dkms_max = version_count[kernel_ver_max]
    if number_dkms_min != number_dkms_max:
        msg = textwrap.dedent(
            """
            {number_dkms_min}  modules for {kernel_ver_min}
            {number_dkms_max}  modules for {kernel_ver_max}
            DKMS module number is inconsistent. Some modules may not be built.
            """.format(
                number_dkms_min=number_dkms_min,
                kernel_ver_min=kernel_ver_min,
                number_dkms_max=number_dkms_max,
                kernel_ver_max=kernel_ver_max,
            )
        )
        print(msg)
        print("=== DKMS status ===\n{0}".format(dkms_status))

    # Scan the APT log for errors during system update
    log_path = "/var/log/apt/term.log"
    err_msg = "Bad return status for module build on kernel: {}".format(
        kernel_ver_current
    )
    with open(log_path, "r") as f:
        if err_msg in f.read():
            print("Found dkms build error messages in {}".format(log_path))
            print("\n=== build log ===")
            result = run_command("grep '{}' {} -C 5".format(err_msg, log_path))
            print(result)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
