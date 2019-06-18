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
import functools
import glob
import os
import subprocess as sp
import textwrap
import time
import shutil
from struct import pack
from socket import inet_ntoa

print = functools.partial(print, flush=True)


def print_head(txt):
    print("##", txt)


def print_cmd(cmd):
    print("+", cmd)


# Configuration file path
if "SNAP_USER_DATA" in os.environ:
    TMP_PATH = os.path.join(os.environ["SNAP_USER_DATA"],
                            "WIFI-TEST-NETPLAN-CREATED-BY-CHECKBOX")
else:
    TMP_PATH = os.path.join("/tmp", "WIFI-TEST-NETPLAN-CREATED-BY-CHECKBOX")

NETPLAN_CFG_PATHS = ("/etc/netplan", "/lib/netplan", "/run/netplan")
NETPLAN_TEST_CFG = "/etc/netplan/99-CREATED-BY-CHECKBOX.yaml"


def netplan_config_backup():
    print_head("Backup any existing netplan configuration files")
    if os.path.exists(TMP_PATH):
        print("Clear backup location")
        shutil.rmtree(TMP_PATH)
    for basedir in NETPLAN_CFG_PATHS:
        print("Checking in {}".format(basedir))
        files = glob.glob(os.path.join(basedir, '*.yaml'))
        if files:
            backup_loc = os.path.join(TMP_PATH, *basedir.split('/'))
            os.makedirs(backup_loc)
            for f in files:
                print(" ", f)
                shutil.copy(f, backup_loc)
    print()


def netplan_config_wipe():
    print_head("Delete any existing netplan configuration files")
    # NOTE: this removes not just configs for wifis, but for all device types
    #  (ethernets, bridges) which could be dangerous
    for basedir in NETPLAN_CFG_PATHS:
        print("Wiping {}".format(basedir))
        files = glob.glob(os.path.join(basedir, '*.yaml'))
        for f in files:
            print(" ", f)
            os.remove(f)

    # If there's any file left in configuration folder then there's something
    # not expected, stop the test
    for basedir in NETPLAN_CFG_PATHS:
        files = glob.glob(os.path.join(basedir, "*.yaml"))
        if files:
            print("ERROR: Failed to wipe netplan config files:")
            for f in files:
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
            restore_loc = f[len(TMP_PATH):]
            print(" ", restore_loc)
            try:
                shutil.move(f, restore_loc)
            except shutil.Error:
                raise SystemExit("Failed to restore {}".format(f))


def generate_test_config(interface, ssid, psk, address, dhcp):
    """
    Produce valid netplan yaml from arguments provided

    Typical open ap with dhcp:

    >>> print(generate_test_config("eth0", "my_ap", None, "", True))
    # This is the network config written by checkbox
    network:
      version: 2
      wifis:
        eth0:
          access-points:
            my_ap: {}
          addresses: []
          dhcp4: True
          nameservers: {}

    Typical private ap with dhcp:

    >>> print(generate_test_config("eth0", "my_ap", "s3cr3t", "", True))
    # This is the network config written by checkbox
    network:
      version: 2
      wifis:
        eth0:
          access-points:
            my_ap: {password: s3cr3t}
          addresses: []
          dhcp4: True
          nameservers: {}

    Static IP no dhcp:
    >>> print(generate_test_config("eth0", "my_ap", "s3cr3t", "192.168.1.1", False))
    # This is the network config written by checkbox
    network:
      version: 2
      wifis:
        eth0:
          access-points:
            my_ap: {password: s3cr3t}
          addresses: [192.168.1.1]
          dhcp4: False
          nameservers: {}
    """
    np_cfg = """\
    # This is the network config written by checkbox
    network:
      version: 2
      wifis:
        {0}:
          access-points:
            {1}: {{{2}}}
          addresses: [{3}]
          dhcp4: {4}
          nameservers: {{}}"""
    if psk:
        password = "password: " + psk
    else:
        password = ""
    return textwrap.dedent(np_cfg.format(interface, ssid, password, address, dhcp))


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
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONUSERBASE', None)
    retcode = sp.call(cmd, shell=True, env=env)
    if retcode != 0:
        print("ERROR: failed netplan apply call")
        return False
    return True


def perform_ping_test(interface):
    """Simple ping test - change to call gateway_ping_test ??"""
    # Get gateway ip for ping test
    server_ip = ""
    with open("/proc/net/route", "r") as route_file:
        for line in route_file:
            if (line.split()[0] == interface
                    and line.split()[1] == "00000000"):
                server_ip = inet_ntoa(
                    pack('<I', int(line.split()[2], 16)))
        if server_ip == "":
            print("Can't find default gateway ip, exiting...")
            return False

    # Test connection by ping
    cmd = "ping -c 5 -I {} {}".format(interface, server_ip)
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    return retcode == 0


def main():
    # Read arguments
    parser = argparse.ArgumentParser(
        description=("This script will test wireless network with netplan"
                     " in client mode."))
    parser.add_argument(
        "-i", "--interface", type=str, help=(
            "The interface which will be tested, default is wlan0"),
        default="wlan0")
    parser.add_argument(
        "-s", "--ssid", type=str, help=(
            "SSID of target network, this is required argument"),
        required=True)
    parser.add_argument(
        "-k", "--psk", type=str, help=(
            "Pre-shared key of target network, this is optional argument,"
            " only for PSK protected network"))
    ip_method = parser.add_mutually_exclusive_group(required=True)
    ip_method.add_argument(
        "-d", "--dhcp", action='store_true', help=(
            "Enable DHCP for IPv4"),
        default=False)
    ip_method.add_argument(
        "-a", "--address", type=str, help=(
            "Set ip address and netmask for the test interface,"
            " example: 192.168.1.1/24"),
        default="")
    args = parser.parse_args()

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
        raise SystemExit(1)
    print()
    time.sleep(20)

    # Check connection by ping or link status
    print_head("Perform a ping test")
    test_result = perform_ping_test(args.interface)
    if test_result:
        print("Connection test passed\n")
    else:
        print("Connection test failed\n")

    delete_test_config()
    netplan_config_restore()

    if not netplan_apply_config():
        raise SystemExit("ERROR: failed to apply restored config")

    if not test_result:
        raise SystemExit(1)


if __name__ == "__main__":
    # Check if executed with root
    if os.geteuid() != 0:
        raise SystemExit("Error: please run this command as root")
    main()
