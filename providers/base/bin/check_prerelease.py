#!/usr/bin/env python3

"""
Script to test that the system is NOT running prerelease software

Copyright (c) 2018 Canonical Ltd.

Authors
   Rod Smith <rod.smith@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

The purpose of this script is to identify whether an EFI-based
system booted from the network (test passes) or from a local disk
(test fails).

Usage:
   check-prerelease.py
"""

import platform
import shlex
import sys

from subprocess import CalledProcessError, check_output


def check_kernel_status():
    """Check kernel to see if it's supported for certification

    :returns:
        True if OK, False if not
    """
    kernel_release = platform.release()

    retval = True
    command = "apt-cache showpkg linux-image-{}".format(kernel_release)
    aptinfo = check_output(shlex.split(command), universal_newlines=True)

    # Exclude kernels that come from obvious PPAs....
    if "ppa.launchpad.net" in aptinfo:
        print("* Kernel appears to have come from a PPA!")
        retval = False

    # Exclude kernels that don't come from the main repo
    if "main_binary" not in aptinfo:
        print("* Kernel does not come from the main Ubuntu repository!")
        retval = False

    try:
        command = "apt-cache show linux-image-{}".format(kernel_release)
        aptinfo = check_output(shlex.split(command), universal_newlines=True)
    except CalledProcessError:
        # "apt-cache show" returns an error status if called on a
        # non-existent package.
        print("* Kernel does not match any installed package!")
        aptinfo = ""
        retval = False

    # Exclude 'edge' kernels, which are identified via the 'Source:' line
    # in the apt-cache show output....
    if "Source: linux-signed-hwe-edge" in aptinfo:
        print("* Kernel is an 'edge' kernel!")
        retval = False
    if "Source: linux-hwe-edge" in aptinfo:
        print("* Kernel is an 'edge' kernel!")
        retval = False

    # Exclude kernels that aren't from the "linux" (or variant, like
    # "linux-hwe" or "linux-signed") source....
    if "Source: linux" not in aptinfo:
        print("* Kernel is not a Canonical kernel!")
        retval = False

    # Exclude low-latency kernels, which are identified via the kernel name
    # string itself....
    if "lowlatency" in kernel_release:
        print("* Kernel is a low-latency kernel!")
        retval = False

    if (not retval):
        print("* Kernel release is {}".format(kernel_release))
        print("* Kernel is ineligible for certification!")

    return retval


def check_os_status():
    """Check OS to see if it's supported for certification. The OS must be
    BOTH an LTS version and a non-development branch to pass this test.

    :returns:
        True if OK, False if not
    """
    retval = True
    command = "lsb_release -s -d"
    lsbinfo = check_output(shlex.split(command), universal_newlines=True)

    # OS information include '(development branch)' on pre-release
    # installations. Such installations should fail this test.
    if "(development branch)" in lsbinfo:
        print("* OS is reported as a development branch:")
        print("* {}".format(lsbinfo))
        retval = False
    print("")

    if "LTS" not in lsbinfo:
        print("* OS is a non-LTS version:")
        print("* {}".format(lsbinfo))
        retval = False

    return retval


def main():
    """Check to see if the machine is running pre-release kernel or OS."""

    retval = 0
    if (not check_kernel_status()):
        retval = 1
    if (not check_os_status()):
        retval += 2
    if (retval == 0):
        print("** All OK; production kernel and OS.")
    elif (retval == 1):
        print("** Test FAILS; running ineligible kernel!")
    elif (retval == 2):
        print("** Test FAILS; running pre-release or non-LTS OS!")
    else:
        print("** Test FAILS; running pre-release OS with ineligible kernel!")

    return(retval)


if __name__ == '__main__':
    sys.exit(main())
