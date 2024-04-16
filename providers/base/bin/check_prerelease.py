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
import logging
import os
import platform
import shlex
import sys

from subprocess import CalledProcessError, check_output


def get_apt_cache_information(command: str):
    """Execute the given apt-cache command and return the information.

    This function runs the specified apt-cache command using the `check_output`
    function, which returns the information about the Linux kernel package
    queried by the command.

    :param command: A string representing the apt-cache command to be executed.

    :return:
        A string containing the information retrieved from the apt-cache
        command.

    :raises CalledProcessError:
        If the apt-cache command returns an empty string with exit code 0,
        indicating a non-existent package.
    :raises SystemExit:
        If the apt-cache command returns an error status, indicating that
        the kernel does not match any installed package.
    """
    try:
        aptinfo = check_output(shlex.split(command), universal_newlines=True)
        # "apt-cache showpkg" returns an empty string with exit code 0 if
        # called on a non-existent package.
        if not aptinfo:
            raise CalledProcessError(returncode=1, cmd=command)
        return aptinfo
    except CalledProcessError as e:
        # "apt-cache show" returns an error status if called on a
        # non-existent package.
        logging.error(e)
        logging.error("* Kernel does not match any installed package!")
        raise SystemExit(1)


def verify_apt_cache_showpkg(kernel_release: str):
    """Check kernel to see if it's supported for certification
        by "apt-cache showpkg linux-image-<kernel_release>"

    :returns:
        True if OK, False if not
    """
    command = "apt-cache showpkg linux-image-{}".format(kernel_release)
    aptinfo = get_apt_cache_information(command)
    # Exclude kernels that come from obvious PPAs....
    retval = True
    if "ppa.launchpad.net" in aptinfo:
        logging.error("* Kernel appears to have come from a PPA!")
        retval = False

    # Exclude kernels that don't come from the specific Ubuntu repository
    target_repo = os.environ.get("KERNEL_REPO", "main")
    if "{}_binary".format(target_repo) not in aptinfo:
        logging.error(
            "* Kernel does not come from the {} Ubuntu repository!".format(
                target_repo
            )
        )
        retval = False
    return retval


def verify_apt_cache_show(kernel_release: str):
    """Check kernel to see if it's supported for certification
        by "apt-cache show linux-image-<kernel_release>"

    :returns:
        True if OK, False if not
    """
    command = "apt-cache show linux-image-{}".format(kernel_release)
    aptinfo = get_apt_cache_information(command)
    retval = True

    # Exclude 'edge' kernels, which are identified via the 'Source:' line
    # in the apt-cache show output....
    for source in ["Source: linux-signed-hwe-edge", "Source: linux-hwe-edge"]:
        if source in aptinfo:
            logging.error("* Kernel is an 'edge' kernel!, found '{}'")
            retval = False

    # Exclude kernels that aren't from the "linux" (or variant, like
    # "linux-hwe" or "linux-signed") source....
    if "Source: linux" not in aptinfo:
        logging.error("* Kernel is not a Canonical kernel!")
        retval = False

    return retval


def verify_not_lowlatency_kernel(kernel_release: str):
    """Check kernel to see if it's supported for certification
        by verifying the "lowlatency" term not in kernel string

    :returns:
        True if OK, False if not
    """
    # Exclude low-latency kernels, which are identified via the kernel name
    # string itself....
    if "lowlatency" in kernel_release:
        logging.error("* Kernel is a low-latency kernel!")
        return False
    return True


def check_kernel_status():
    """Check kernel to see if it's supported for certification

    :returns:
        True if OK, False if not
    """
    kernel_release = platform.release()
    logging.info("* Kernel release is {}".format(kernel_release))

    is_valid_kernel = True
    is_valid_kernel &= verify_apt_cache_showpkg(kernel_release)
    is_valid_kernel &= verify_apt_cache_show(kernel_release)
    is_valid_kernel &= verify_not_lowlatency_kernel(kernel_release)

    if not is_valid_kernel:
        logging.error("* Kernel is ineligible for certification!")

    return is_valid_kernel


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
    if not check_kernel_status():
        retval = 1
    if not check_os_status():
        retval += 2
    if retval == 0:
        print("** All OK; production kernel and OS.")
    elif retval == 1:
        print("** Test FAILS; running ineligible kernel!")
    elif retval == 2:
        print("** Test FAILS; running pre-release or non-LTS OS!")
    else:
        print("** Test FAILS; running pre-release OS with ineligible kernel!")

    return retval


if __name__ == "__main__":
    sys.exit(main())
