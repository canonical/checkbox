#!/usr/bin/env python3
import sys
import copy
import logging
import argparse
from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.system import get_gadget_snap


def register_arguments():
    parser = argparse.ArgumentParser(
        description="Validate the slot and plug interface"
    )
    parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=["plug", "slot"],
        help="the interface type of snap",
    )
    parser.add_argument("--name", type=str, required=True)
    parser.add_argument("--interface", type=str, required=True)
    parser.add_argument("--attrs", type=str)
    return parser.parse_args()


def filter_gadget_interface(type):
    gadget_snap = get_gadget_snap()
    interface_key = "{}s".format(type)
    system_snap_interfaces = Snapd().interfaces()[interface_key]

    for interface in copy.deepcopy(system_snap_interfaces):
        if interface["snap"] != gadget_snap:
            system_snap_interfaces.remove(interface)

    return system_snap_interfaces


def varify_slot_interface(name, interface):
    logging.info(
        "[Expected Slot Interface] name: %s, type: %s", name, interface
    )
    gadget_interfaces = filter_gadget_interface("slot")
    for sys_intf in gadget_interfaces:
        if sys_intf["slot"] != name:
            continue

        logging.info(
            "[Actual Slot Interface] name: %s, type: %s\n",
            sys_intf["slot"],
            sys_intf["interface"],
        )
        if sys_intf["interface"] == interface:
            logging.info(
                "The interface type of %s slot interface match", name
            )
            exit(0)
        else:
            logging.error(
                "The interface type of %s slot interface mismatch", name
            )
            exit(1)

    logging.error("The %s slot interface is not defined in gadget", name)
    exit(1)


def varify_plug_interface(name, interface):
    logging.info(
        "[Expected Plug Interface] name: %s, type: %s", name, interface
    )

    gadget_interfaces = filter_gadget_interface("plug")

    for sys_intf in gadget_interfaces:
        if sys_intf["plug"] != name:
            continue

        logging.info(
            "[Actual Plug Interface] name: %s, type: %s\n",
            sys_intf["plug"],
            sys_intf["interface"],
        )
        if sys_intf["interface"] == interface:
            logging.info(
                "The interface type of %s plug interface match", name
            )
            exit(0)
        else:
            logging.error(
                "The interface type of %s plug interface mismatch", name
            )
            exit(1)

    logging.error("The %s plug interface is not defined in gadget", name)
    exit(1)


def main():
    args = register_arguments()

    if args.type == "slot":
        # AI: to verify the slot attrs
        varify_slot_interface(args.name, args.interface)
    elif args.type == "plug":
        varify_plug_interface(args.name, args.interface)
    else:
        raise ValueError("Unsupported action")


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.basicConfig(
        level=logging.ERROR,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),
        ],
    )
    main()
