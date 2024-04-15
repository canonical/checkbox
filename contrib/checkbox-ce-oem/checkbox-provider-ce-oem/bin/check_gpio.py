#!/usr/bin/env python3
import argparse
import os
from contextlib import contextmanager

# from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.system import get_gadget_snap
import requests


def list_gpio_slots(snapd, gadget_name):
    """
    List GPIO slots defined by a gadget snap.

    Args:
        snapd: A Snapd object for interacting with Snapd.
        gadget_name: The name of the gadget snap.

    Returns:
        A dictionary containing GPIO slot information.
    """

    gpio_slot = {}

    # Go through whole response of "Snapd.interface()", and parser out
    # the interfaces that is GPIO and define by gadget snap.
    for slots in snapd.interfaces()["slots"]:
        if slots["interface"] == "gpio" and slots["snap"] == gadget_name:
            gpio_slot[slots["slot"]] = {"number": slots["attrs"]["number"]}
    return gpio_slot


def parse_config(config):
    """
    Parse a configuration string containing port numbers or ranges
    of port numbers.

    Args:
        config (str): A comma-separated string containing port numbers
        or ranges of port numbers.
        Port ranges are specified using the format 'start:end'.

    Returns:
        list: A list containing all the port numbers parsed from
        the configuration string.

    Example:
        >>> parse_config("1,2,5:7,10")
        [1, 2, 5, 6, 7, 10]
    """

    expect_port = []
    if config:
        for port_list in config.split(","):
            if ":" not in port_list:
                expect_port.append(int(port_list))
            else:
                start_port = port_list.split(":")[0]
                end_port = port_list.split(":")[1]
                try:
                    start_port = int(start_port)
                    end_port = int(end_port)
                    if start_port > end_port:
                        raise ValueError(
                            "Invalid port range: {}".format(port_list)
                        )
                    for range_port in range(start_port, end_port + 1):
                        expect_port.append(range_port)
                except ValueError:
                    raise ValueError(
                        "Invalid port range: {}".format(port_list)
                    )
    else:
        raise ValueError("Error: Config is empty!")
    return expect_port


def check_gpio_list(gpio_list, config):
    """
    Check if all expected GPIO numbers are defined in the gadget snap.

    Args:
        gpio_list: A dictionary containing GPIO slot information.
        config: Checkbox config including expected GPIO numbers.
            e.g. EXPECTED_GADGET_GPIO=499,500,501:504
                 Sprate by comma, and also colon to define a range of ports

    Raises:
        SystemExit: If any expected GPIO slot is not defined in the gadget
        snap.
    """
    if gpio_list:
        expect_port = parse_config(config)
        for gpio in gpio_list.values():
            if gpio["number"] in expect_port:
                expect_port.remove(gpio["number"])
        if expect_port:
            for gpio_slot in expect_port:
                print(
                    "Error: Slot of GPIO {} is not defined in gadget snap".format(
                        gpio_slot
                    )
                )
            raise SystemExit(1)
        else:
            print("All expected GPIO slots have been defined in gadget snap.")
    else:
        raise SystemExit("Error: No any GPIO slots existed!")


@contextmanager
def interface_test(gpio_slot, gadget_name, timeout=60):
    snap = os.environ["SNAP_NAME"]
    timeout = int(os.environ.get("SNAPD_TASK_TIMEOUT", timeout))
    try:
        connect_interface(gadget_name, gpio_slot, snap, timeout)
        yield
    finally:
        disconnect_interface(gadget_name, gpio_slot, snap, timeout)


def connect_interface(gadget_name, gpio_slot, snap, timeout):
    """
    Connect GPIO plugs of checkbox to GPIO slots of gadget snap.

    Args:
        gpio_slot: A GPIO slot information.
        gadget_name: The name of the gadget snap.

    Raises:
        SystemExit: If failed to connect any GPIO.
    """

    # Get the snap name of checkbox
    print("Attempting connect GPIO to {}:{}".format(gadget_name, gpio_slot))
    try:
        Snapd(task_timeout=timeout).connect(
            gadget_name, gpio_slot, snap, "gpio"
        )
        print("Success")
    except requests.HTTPError:
        print("Failed to connect {}".format(gpio_slot))
        raise SystemExit(1)


def disconnect_interface(gadget_name, gpio_slot, snap, timeout):
    """
    Connect GPIO plugs of checkbox to GPIO slots of gadget snap.

    Args:
        gpio_slot: A GPIO slot information.
        gadget_name: The name of the gadget snap.

    Raises:
        SystemExit: If failed to connect any GPIO.
    """

    # Get the snap name of checkbox
    print(
        "Attempting disconnect GPIO slot {}:{}".format(gadget_name, gpio_slot)
    )
    try:
        Snapd(task_timeout=timeout).disconnect(
            gadget_name, gpio_slot, snap, "gpio"
        )
        print("Success")
    except requests.HTTPError:
        print("Failed to disconnect {}".format(gpio_slot))
        raise SystemExit(1)


def check_node(num):
    """
    Check if a GPIO node is exported.

    Args:
        num: The GPIO number to check.

    Raises:
        SystemExit: If the GPIO node does not exist.
    """

    path = "/sys/class/gpio/gpio{}".format(num)
    if os.path.exists(path):
        print("GPIO node of {} exist!".format(num))
    else:
        raise SystemExit("GPIO node of {} not exist!".format(num))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="action",
        help="Action in check-gpio, check-node and dump",
    )
    check_gpio_subparser = subparsers.add_parser("check-gpio")
    check_gpio_subparser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Checkbox config include expected GPIO\
             e.g. 499:500:501:502",
    )
    check_node_subparser = subparsers.add_parser("check-node")
    check_node_subparser.add_argument(
        "-n",
        "--num",
        type=int,
        required=True,
        help="GPIO number to check if node exported",
    )
    check_node_subparser.add_argument(
        "-s",
        "--slot",
        type=str,
        required=True,
        help="GPIO slot to connect.",
    )
    subparsers.add_parser("dump", help="Dump GPIO slots from gadget")
    args = parser.parse_args()
    snapd = Snapd()
    gadget_name = get_gadget_snap()
    gpio_slots = list_gpio_slots(snapd, gadget_name)
    if args.action == "check-gpio":
        check_gpio_list(gpio_slots, args.config)
    if args.action == "dump":
        for x in gpio_slots:
            print(
                "slot: {}\ngpio_number: {}\n".format(
                    x, gpio_slots[x]["number"]
                )
            )
    if args.action == "check-node":
        with interface_test(args.slot, gadget_name):
            check_node(args.num)


if __name__ == "__main__":
    main()
