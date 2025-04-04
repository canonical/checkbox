#!/usr/bin/env python3
"""
Scripts used to test sriov network functions
Copyright (C) 2025 Canonical Ltd.

Author
    Michael Reed <michael.reed@canonical.com.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import logging
import os
import sys
import distro

from checkbox_support.lxd_support import LXD, LXDVM

# Map vendor IDs to vendor names
VENDOR_INFO = {
    "0x8086": ("Intel"),
    "0x15b3": ("Mellanox"),
    "0x14e4": ("Broadcom"),
}

# Number of virutal interfaces created for SRIOV Enabled Interfaces
NUM_OF_VIRTUAL_IFACES = 1


def check_ubuntu_version():
    logging.info("Check for 24.04 or greater")
    try:
        # Get distro information
        version = distro.version()

        # Check if the OS is Ubuntu and the version is greater than 24.04
        if float(version) < 24.04:
            logging.info(
                "24.04 or greater is required, this is {}".format(version)
            )
            sys.exit(1)
        else:
            logging.info("The system is 24.04 or greater, proceed")
    except Exception as e:
        logging.info("An error occurred: {}".format(e))
        sys.exit(1)


def check_interface_vendor(interface):
    """
    Find the vendor of the network interface
    """
    vendor_id_path = "/sys/class/net/{}/device/vendor".format(interface)

    try:
        if os.path.exists(vendor_id_path):
            with open(vendor_id_path, "r") as file:
                vendor_id = file.read().strip()

        if vendor_id in VENDOR_INFO:
            vendor_name = VENDOR_INFO[vendor_id]
            if vendor_name != "Broadcom":
                logging.info(
                    "The interface {} is a(n) {} NIC".format(
                        interface, vendor_name
                    )
                )
            else:
                logging.info(
                    "Broadcom SRIOV testing is not supported at this time"
                )
                sys.exit(1)
        else:
            logging.info(
                "{} has an unknown vendor  ID {}".format(interface, vendor_id)
            )
            sys.exit(1)

    except Exception as e:
        logging.info("An error occurred: {}".format(e))
        sys.exit(1)


def is_sriov_capable(interface):
    """
    Check if the specified network interface is SR-IOV capable and
    configured to support at least one Virtual Function.
    """
    sriov_path = "/sys/class/net/{}/device/sriov_numvfs".format(interface)
    num_vfs = NUM_OF_VIRTUAL_IFACES

    try:
        # Check if the interface supports SR-IOV
        logging.info("checking if sriov_numvfs exits")
        if not os.path.exists(sriov_path):
            logging.error(
                "SR-IOV not supported or interface {} \
                          does not exist.".format(
                    interface
                )
            )
        else:
            logging.info(
                "SR-IOV before change {} VFs on interface {}.".format(
                    num_vfs, interface
                )
            )
            # First, disable VFs before changing the number to avoid issues
            logging.info("setting numvfs to zero")
            with open(sriov_path, "w") as f:
                f.write("0")

            # Set the desired number of VFs
            with open(sriov_path, "w") as f:
                f.write(str(num_vfs))

            logging.info(
                "SR-IOV enabled with {} VFs on interface {}.".format(
                    num_vfs, interface
                )
            )

    except (IOError, FileNotFoundError) as e:
        logging.info("Failed to enable SR-IOV on {}: {}".format(interface, e))
        sys.exit(1)

    except Exception as e:
        logging.info("An error occurred: {}".format(e))
        sys.exit(1)


def test_lxd_sriov(args):
    logging.info("Starting lxd SRIOV Test")
    verify_cmds = 'bash -c "lspci | grep Virtual"'
    options = ["--network", "lab_sriov"]
    network_cmd = "lxc network create lab_sriov --type=sriov parent={}".format(
        args.interface
    )

    check_ubuntu_version()
    check_interface_vendor(args.interface)
    is_sriov_capable(args.interface)

    instance = LXD(args.template, args.rootfs)
    with LXD(args.template, args.rootfs) as instance:
        logging.info("Create sriov network for lxc")
        instance.run("lxc network delete lab_sriov", ignore_errors=True)
        instance.run(network_cmd)

        logging.info("Launching container: %s", instance.name)
        instance.launch(options)

        logging.info("Waiting for %s to be up", instance.name)
        instance.wait_until_running()

        instance.run(verify_cmds, on_guest=True)

    instance.run("lxc network delete lab_sriov")


def test_lxd_vm_sriov(args):
    logging.info("Starting lxd vm SRIOV")
    verify_cmds = 'bash -c "lspci | grep Virtual"'
    options = ["-c", "security.secureboot=false", "--network", "lab_sriov"]
    network_cmd = "lxc network create lab_sriov --type=sriov parent={}".format(
        args.interface
    )

    check_ubuntu_version()
    check_interface_vendor(args.interface)
    is_sriov_capable(args.interface)

    with LXDVM(args.template, args.image) as instance:
        logging.info("Create sriov network for lxc vm")
        instance.run("lxc network delete lab_sriov", ignore_errors=True)
        instance.run(network_cmd)

        logging.info("Launching virtual machine: %s", instance.name)
        instance.launch(options)

        logging.info("Waiting for %s to be up", instance.name)
        instance.wait_until_running()

        logging.info("running a simple command")
        instance.run(verify_cmds, on_guest=True)

    instance.run("lxc network delete lab_sriov")


def main():

    parser = argparse.ArgumentParser(description="SRIOV Test")
    subparsers = parser.add_subparsers()

    # Main cli options
    lxd_sriov_parser = subparsers.add_parser(
        "lxd", help=("Run the SRIOV test on LXD validation test")
    )
    lxd_vm_sriov_parser = subparsers.add_parser(
        "lxdvm", help=("Run the SRIOV test on VM validation test")
    )

    parser.add_argument(
        "--debug",
        dest="log_level",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
    )

    parser.add_argument(
        "--interface", type=str, default=None, help="SRIOV Interface"
    )

    # Sub test options
    lxd_sriov_parser.add_argument(
        "--template", type=str, default=os.getenv("LXD_TEMPLATE")
    )

    lxd_sriov_parser.add_argument(
        "--rootfs", type=str, default=os.getenv("LXD_ROOTFS")
    )

    lxd_sriov_parser.set_defaults(func=test_lxd_sriov)

    # Sub test options
    lxd_vm_sriov_parser.add_argument(
        "--template", type=str, default=os.getenv("LXD_TEMPLATE")
    )

    lxd_vm_sriov_parser.add_argument(
        "--image", type=str, default=os.getenv("KVM_IMAGE")
    )

    lxd_vm_sriov_parser.set_defaults(func=test_lxd_vm_sriov)

    args = parser.parse_args()

    try:
        logging.basicConfig(level=args.log_level)
    except AttributeError:
        pass

    # silence normal output from requests module
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Verify args
    try:
        args.func(args)
    except AttributeError:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
