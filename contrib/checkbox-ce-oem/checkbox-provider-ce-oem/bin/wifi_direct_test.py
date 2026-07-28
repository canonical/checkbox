#!/usr/bin/env python3

import argparse
import subprocess
import re
import os
import logging
import sys
import time
import shlex
from contextlib import contextmanager

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


def runcmd(command):
    """Excute command by subprocess

    Args:
        command (str): command to excute
    """
    proc = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc


def get_mac_by_interface(interface="p2p0"):
    """get mac address by interface name"""
    # Use the ip command to get interface details
    result = runcmd(f"ip link show {interface}")
    if result.returncode != 0:
        sys.exit("Error: {}".format(result.stderr.strip()))

    # Extract the MAC address using regex
    mac_address = re.search(
        r"ether ([0-9a-fA-F:]{17})", result.stdout.decode()
    )
    if mac_address:
        return mac_address.group(1)
    else:
        sys.exit("Error: MAC address not found for {}".format(interface))


def connect_to_pair_device(args):
    """Connect to pair p2p device"""

    mac = get_mac_by_interface(args.interface)
    logging.info("Make sure the pair device is in pairable state")
    logging.info("Press enter to continue")
    input()
    discover_nearby_device(args)

    logging.info("starting connection.... ")
    if args.role == "autonomous-go":
        logging.info("Adding local end as group owner...")
        runcmd("wpa_cli -i{} p2p_group_add".format(args.interface))
        runcmd("wpa_cli -i{} wps_pbc".format(args.interface))
        logging.info(
            (
                "Run command on pair device to establish the connection\n"
                "$ wpa_cli p2p_connect %s pbc join"
            ),
            mac,
        )
    else:
        command = "wpa_cli -i{} p2p_connect {} pbc go_intent={}".format(
            args.interface, args.pair_mac, 0 if args.role == "client" else 15
        )
        runcmd(command)
        logging.info(
            (
                "Run command on pair device to establish the connection\n"
                "$ wpa_cli p2p_connect %s pbc"
            ),
            mac,
        )

    sys.stdout.flush()
    time.sleep(15)
    logging.info("Press enter to continue")
    input()

    # check p2p status
    command = "wpa_cli -i{} status".format(args.interface)
    ret = runcmd(command)
    logging.info(
        "{} status\n{}".format(
            args.interface, ret.stdout.decode(sys.stdout.encoding)
        )
    )
    time.sleep(1)
    logging.info("Check if the connection is established")
    logging.info("Press enter to continue")
    input()


def discover_nearby_device(args):
    """Discover nearby p2p devices"""
    command = "wpa_cli -i{} p2p_find".format(args.interface)
    logging.info("Scanning nearby devices...")
    process = runcmd(command)
    if process.returncode != 0:
        logging.error("Unable to activate p2p_find")
        raise SystemError(1)

    time.sleep(10)
    command = "wpa_cli -i{} p2p_stop_find".format(args.interface)
    logging.info("Stop scanning nearby devices")
    runcmd(command)


@contextmanager
def wpa_supplicant_pre_setup(args):
    config_dir = "/tmp/p2p_supplicant.conf"
    default_config = [
        "ctrl_interface=/var/run/wpa_supplicant\n",
        "update_config=1\n",
        "device_name=p2p_test_DUT\n",
        "device_type=1-0050F204-1\n",
        "config_methods=virtual_push_button physical_display keypad\n",
        "p2p_ssid_postfix=-p2p\n",
        "persistent_reconnect=1\n",
        "p2p_no_group_iface=1\n",
        "p2p_listen_channel=1\n",
        "pmf=1\n",
    ]
    # Configure P2P Wi-Fi mode
    mode_config = {
        "ht": "p2p_go_ht40=1\n",
        "vht": "p2p_go_vht=1\n",
        "he": "p2p_go_he=1\n",
    }
    default_config.append(mode_config[args.mode])

    # Configure channel preferences
    channel_config = {
        "6": "p2p_pref_chan=81:6\n",
        "149": "p2p_pref_chan=124:149\n",
    }
    default_config.append(channel_config[args.channel])

    try:
        with open(config_dir, "w+") as config_file:
            config_file.writelines(default_config)

        # terminate wap_supplicant if present
        command = "wpa_cli -i{} terminate".format(args.interface)
        runcmd(command)

        # start wpa_supplicant
        command = "wpa_supplicant -i{} -Dnl80211 -c {}".format(
            args.interface, config_dir
        )

        logging.info("initializing wpa_supplicant...")
        wpa_proc = subprocess.Popen(
            shlex.split(command), universal_newlines=True
        )
        time.sleep(3)
        yield wpa_proc

    finally:
        # terminate wap_supplicant
        command = "wpa_cli -i{} terminate".format(args.interface)
        runcmd(command)

        if os.path.exists(config_dir):
            os.remove(config_dir)


def register_arguments():
    """Register arguments for the Wi-Fi P2P"""
    parser = argparse.ArgumentParser(description="Wi-Fi P2P parser")

    # create subcommand
    parser.add_argument(
        "command",
        choices=["connect", "discover"],
        help="Operations choices: connect or discover",
    )

    # Common arguments
    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        required=True,
        help="Target interface (e.g., p2p0)",
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        default="vht",
        choices=["ht", "vht", "he"],
        help="Wireless mode (default: vht)",
    )
    parser.add_argument(
        "-ch",
        "--channel",
        type=str,
        default="6",
        help="Preferred channel (default: 6)",
    )

    # arguments needed for connec
    parser.add_argument(
        "-p",
        "--pair-mac",
        type=str,
        help="Pair device's MAC address (required for 'connect')",
    )
    parser.add_argument(
        "-r",
        "--role",
        type=str,
        choices=["autonomous-go", "negotiation-go", "client"],
        default="autonomous-go",
        help="Connecting role (default: autonomous-go)",
    )

    return parser


def main():
    # Register and parse arguments
    parser = register_arguments()
    args = parser.parse_args()

    if args.command == "connect":
        if not args.pair_mac:
            parser.error("'--pair-mac' is required for the 'connect' command")
        with wpa_supplicant_pre_setup(args):
            connect_to_pair_device(args)
    elif args.command == "discover":
        with wpa_supplicant_pre_setup(args):
            discover_nearby_device(args)


if __name__ == "__main__":
    main()
