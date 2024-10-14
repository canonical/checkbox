#!/usr/bin/env python3
# Copyright 2018-2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Gavin Lin <gavin.lin@canonical.com>
#    Jonathan Cave <jonathan.cave@canonical.com>

"""
This script will test Wi-Fi device with netplan automatically.

To see how to use, please run "./wifi_client_test_netplan.py --help"
"""

import argparse
import datetime
import functools
import glob
import os
import subprocess as sp
import textwrap
import time
import shutil
import sys
import ipaddress
import yaml

from gateway_ping_test import ping

print = functools.partial(print, flush=True)


def print_head(txt):
    print("##", txt)


def print_cmd(cmd):
    print("+", cmd)


# Configuration file path
if "SNAP_USER_DATA" in os.environ:
    TMP_PATH = os.path.join(
        os.environ["SNAP_USER_DATA"], "WIFI-TEST-NETPLAN-CREATED-BY-CHECKBOX"
    )
else:
    TMP_PATH = os.path.join("/tmp", "WIFI-TEST-NETPLAN-CREATED-BY-CHECKBOX")

NETPLAN_CFG_PATHS = ("/etc/netplan", "/lib/netplan", "/run/netplan")
NETPLAN_TEST_CFG = "/etc/netplan/99-CREATED-BY-CHECKBOX.yaml"


def netplan_renderer():
    """
    Check the renderer used by netplan on the system.
    This function looks for the renderer used in the yaml files located in the
    NETPLAN_CFG_PATHS directories, and returns the first renderer found. If the
    renderer is not found, it defaults to "networkd".
    """
    for basedir in NETPLAN_CFG_PATHS:
        if os.path.exists(basedir):
            files = glob.glob(os.path.join(basedir, "*.yaml"))
            for f in files:
                with open(f, "r") as file:
                    data = yaml.safe_load(file)
                    if "renderer" in data["network"]:
                        return data["network"]["renderer"]
    return "networkd"


def check_and_get_renderer(renderer):
    """
    Check if the renderer provided matches the one used by netplan. If the
    renderer is set to "AutoDetect", it will return the detected renderer.
    """
    machine_renderer = netplan_renderer()

    if renderer == "AutoDetect":
        return machine_renderer
    elif renderer != machine_renderer:
        raise SystemExit(
            "ERROR: Renderer mismatch, expected: {}, got: {}".format(
                machine_renderer, renderer
            )
        )
    return renderer


def get_netplan_config_files():
    config_files = []
    for basedir in NETPLAN_CFG_PATHS:
        if os.path.exists(basedir):
            files = glob.glob(os.path.join(basedir, "*.yaml"))
            config_files.extend(files)
    return config_files


def netplan_config_backup():
    print_head("Backup any existing netplan configuration files")
    if os.path.exists(TMP_PATH):
        print("Clear backup location")
        shutil.rmtree(TMP_PATH)

    config_files = get_netplan_config_files()

    for f in config_files:
        basedir = os.path.dirname(f)
        print("Backing up from {}".format(basedir))
        backup_loc = os.path.join(TMP_PATH, *basedir.split("/"))
        os.makedirs(backup_loc, exist_ok=True)
        print(" ", f)
        shutil.copy(f, backup_loc)
    print()


def netplan_config_wipe():
    print_head("Delete any existing netplan configuration files")
    config_files = get_netplan_config_files()
    for f in config_files:
        print(" ", f)
        os.remove(f)

    # If there's any file left in configuration folder then there's something
    # not expected, stop the test
    remaining_files = get_netplan_config_files()
    if remaining_files:
        print("ERROR: Failed to wipe netplan config files:")
        for f in remaining_files:
            print(" ", f)
        netplan_config_restore()
        raise SystemExit("Configuration file restored, exiting...")
    print()


def netplan_config_restore():
    print_head("Restore configuration files")
    files = glob.glob("{}/**/*.yaml".format(TMP_PATH), recursive=True)
    if files:
        print("Restoring:")
        for f in files:
            restore_loc = f[len(TMP_PATH) :]
            print(" ", restore_loc)
            try:
                shutil.move(f, restore_loc)
            except shutil.Error:
                raise SystemExit("Failed to restore {}".format(f))


def generate_test_config(interface, ssid, psk, address, dhcp, wpa3, renderer):
    """
    Produce valid netplan yaml from arguments provided

    Typical open ap with dhcp:
    # This is the network config written by checkbox
    network:
      version: 2
      renderer: networkd
        wifis:
          eth0:
            access-points:
            my_ap:
              auth:
                password: s3cr3t
            dhcp4: true
            nameservers: {}
    """
    if not ssid:
        raise SystemExit("A SSID is required for the test")
    # Define the access-point with the ssid
    access_point = {ssid: {}}
    # If psk is provided, add it to the "auth" section
    if psk:
        access_point[ssid] = {"auth": {"password": psk}}
        # Set the key-management to "sae" when WPA3 is used
        if wpa3:
            access_point[ssid]["auth"]["key-management"] = "sae"
        else:
            access_point[ssid]["auth"]["key-management"] = "psk"

    # Define the interface_info
    interface_info = {
        "access-points": access_point,
        "dhcp4": dhcp,
        "nameservers": {},
    }

    # If address is provided, add it to the interface_info
    if address:
        interface_info["addresses"] = [address]

    network_config = {
        "network": {
            "version": 2,
            "renderer": renderer,
            "wifis": {interface: interface_info},
        }
    }

    # Serialize the dictionary to a YAML string using pyyaml
    yaml_output = yaml.safe_dump(network_config, default_flow_style=False)
    output = textwrap.dedent(
        "# This is the network config written by checkbox\n" + yaml_output
    )
    return output


def write_test_config(config):
    print_head("Write the test netplan config file to disk")
    with open(NETPLAN_TEST_CFG, "w", encoding="utf-8") as f:
        f.write(config)
    print()


def delete_test_config():
    print_head("Delete the test file")
    os.remove(NETPLAN_TEST_CFG)
    print()


def netplan_apply_config():
    cmd = "netplan --debug apply"
    print_cmd(cmd)
    # Make sure the python env used by netplan is from the base snap
    env = os.environ
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONUSERBASE", None)
    retcode = sp.call(cmd, shell=True, env=env)
    if retcode != 0:
        print("ERROR: failed netplan apply call")
        print()
        return False
    print()
    return True


def get_interface_info(interface, renderer):
    if renderer == "networkd":
        cmd = "networkctl status --no-pager --no-legend {}".format(interface)
        key_map = {"State": "state", "Gateway": "gateway"}
    elif renderer == "NetworkManager":
        cmd = "nmcli device show {}".format(interface)
        key_map = {"GENERAL.STATE": "state", "IP4.GATEWAY": "gateway"}
    else:
        raise ValueError("Unknown renderer: {}".format(renderer))

    return _get_cmd_info(cmd, key_map, renderer)


def _get_cmd_info(cmd, key_map, renderer):
    info = {}
    try:
        output = sp.check_output(cmd, shell=True)
        for line in output.decode(sys.stdout.encoding).splitlines():
            # Skip lines that don't have a "key: value" format
            if ":" not in line:
                continue
            key, val = line.strip().split(":", maxsplit=1)
            key = key.strip()
            val = val.strip()
            if key in key_map:
                info[key_map[key]] = val
    except sp.CalledProcessError as e:
        print("Error running {} command: {}".format(renderer, e))
    return info


def _check_routable_state(interface, renderer):
    """
    Check if the interface is in a routable state depending on the renderer
    """
    routable = False
    state = ""
    info = get_interface_info(interface, renderer)
    state = info.get("state", "")
    if renderer == "networkd":
        routable = "routable" in state
    elif renderer == "NetworkManager":
        routable = "connected" in state and "disconnected" not in state
    else:
        raise ValueError("Unknown renderer: {}".format(renderer))
    return (routable, state)


def wait_for_routable(interface, renderer, max_wait=30):
    attempts = 0
    routable = False
    state = ""
    while not routable and attempts < max_wait:
        (routable, state) = _check_routable_state(interface, renderer)
        time.sleep(1)
        attempts += 1

    if routable:
        print("Reached routable state")
    else:
        if "degraded" in state:
            print("ERROR: degraded state, no IP address assigned")
        else:
            print("ERROR: did not reach routable state")
    print()
    return routable


def print_address_info(interface):
    cmd = "ip address show dev {}".format(interface)
    print_cmd(cmd)
    sp.call(cmd, shell=True)
    print()


def print_route_info():
    cmd = "ip route"
    print_cmd(cmd)
    sp.call(cmd, shell=True)
    print()


def _validate_gateway_ip(gateway):
    if not gateway:
        return ""
    # Check if the gateway is a valid IP address
    # Examples:
    # 192.168.144.1 (TP-Link 123)
    # 192.168.144.1
    ip_part = gateway.split()[0]  # Get the first part before any space
    return ip_part if __validate_ip(ip_part) else ""


def __validate_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def get_gateway(interface, renderer):
    info = get_interface_info(interface, renderer)
    gateway = info.get("gateway") or ""
    validated_gateway = _validate_gateway_ip(gateway)
    print("Got gateway address: {}".format(gateway))
    print("Validated gateway address: {}".format(validated_gateway))
    return validated_gateway


def perform_ping_test(interface, renderer):
    target = get_gateway(interface, renderer)

    if target:
        count = 5
        result = ping(target, interface, count, 10)
        print("Ping result: {}".format(result))
        if result["received"] == count:
            return True

    return False


def print_journal_entries(start, renderer):
    if renderer == "networkd":
        render_service = "systemd-networkd.service"
    elif renderer == "NetworkManager":
        render_service = "NetworkManager.service"
    else:
        raise ValueError("Unknown renderer: {}".format(renderer))
    print_head("Journal Entries")
    cmd = (
        "journalctl -q --no-pager "
        "-u {} "
        "-u wpa_supplicant.service "
        "-u netplan-* "
        '--since "{}" '.format(
            render_service, start.strftime("%Y-%m-%d %H:%M:%S")
        )
    )
    print_cmd(cmd)
    sp.call(cmd, shell=True)


def parse_args():
    # Read arguments
    parser = argparse.ArgumentParser(
        description=(
            "This script will test wireless network with netplan"
            " in client mode."
        )
    )
    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        help=("The interface which will be tested, default is wlan0"),
        default="wlan0",
    )
    parser.add_argument(
        "-s",
        "--ssid",
        type=str,
        help=("SSID of target network, this is required argument"),
        required=True,
    )
    parser.add_argument(
        "-k",
        "--psk",
        type=str,
        help=(
            "Pre-shared key of target network, this is optional argument,"
            " only for PSK protected network"
        ),
    )
    ip_method = parser.add_mutually_exclusive_group(required=True)
    ip_method.add_argument(
        "-d",
        "--dhcp",
        action="store_true",
        help=("Enable DHCP for IPv4"),
        default=False,
    )
    ip_method.add_argument(
        "-a",
        "--address",
        type=str,
        help=(
            "Set ip address and netmask for the test interface,"
            " example: 192.168.1.1/24"
        ),
        default="",
    )
    parser.add_argument(
        "--wpa3",
        action="store_true",
        help=("Configure WPA3 key management for the network"),
        default=False,
    )

    parser.add_argument(
        "--renderer",
        choices=["networkd", "NetworkManager", "AutoDetect"],
        help=(
            "Set the backend daemon to use for netplan configuration. "
            "If 'AutoDetect' is set, the script will try to determine the "
            "renderer based on the system configuration. "
            "(default: %(default)s)"
        ),
        default="AutoDetect",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    start_time = datetime.datetime.now()

    renderer = check_and_get_renderer(args.renderer)
    args.renderer = renderer
    netplan_config_backup()
    netplan_config_wipe()

    # Create wireless network test configuration file
    print_head("Generate a test netplan configuration")
    config_data = generate_test_config(**vars(args))
    print(config_data)
    print()

    write_test_config(config_data)

    # Bring up the interface
    print_head("Apply the test configuration")
    if not netplan_apply_config():
        delete_test_config()
        netplan_config_restore()
        print_journal_entries(start_time, renderer)
        raise SystemExit(1)
    time.sleep(20)

    print_head("Wait for interface to be routable")
    reached_routable = wait_for_routable(args.interface, renderer)

    test_result = False
    if reached_routable:
        print_head("Display address")
        print_address_info(args.interface)

        print_head("Display route table")
        print_route_info()

        # Check connection by ping or link status
        print_head("Perform a ping test")
        test_result = perform_ping_test(args.interface, renderer)
        if test_result:
            print("Connection test passed\n")
        else:
            print("Connection test failed\n")

    delete_test_config()
    netplan_config_restore()

    if not netplan_apply_config():
        print_journal_entries(start_time, renderer)
        raise SystemExit("ERROR: failed to apply restored config")

    if not test_result:
        print_journal_entries(start_time, renderer)
        raise SystemExit(1)

    print_journal_entries(start_time, renderer)


if __name__ == "__main__":
    # Check if executed with root
    if os.geteuid() != 0:
        raise SystemExit("Error: please run this command as root")
    main()
