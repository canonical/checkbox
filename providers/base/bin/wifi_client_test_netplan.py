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

from gateway_ping_test import ping

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
    >>> print(generate_test_config(
        "eth0", "my_ap", "s3cr3t", "192.168.1.1", False))
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
    return textwrap.dedent(np_cfg.format(interface, ssid, password,
                                         address, dhcp))


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
        print()
        return False
    print()
    return True


def _get_networkctl_state(interface):
    cmd = 'networkctl status --no-pager --no-legend {}'.format(interface)
    output = sp.check_output(cmd, shell=True)
    for line in output.decode(sys.stdout.encoding).splitlines():
        key, val = line.strip().split(':', maxsplit=1)
        if key == "State":
            return val


def wait_for_routable(interface, max_wait=30):
    routable = False
    attempts = 0
    while not routable and attempts < max_wait:
        state = _get_networkctl_state(interface)
        print(state)
        if "routable" in state:
            routable = True
            break
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
    cmd = 'ip address show dev {}'.format(interface)
    print_cmd(cmd)
    sp.call(cmd, shell=True)
    print()


def print_route_info():
    cmd = 'ip route'
    print_cmd(cmd)
    sp.call(cmd, shell=True)
    print()


def perform_ping_test(interface):
    target = None
    cmd = 'networkctl status --no-pager --no-legend {}'.format(interface)
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    for line in output.decode(sys.stdout.encoding).splitlines():
        vals = line.strip().split(' ')
        if len(vals) >= 2:
            if vals[0] == 'Gateway:':
                target = vals[1]
                print('Got gateway address: {}'.format(target))

    if target:
        count = 5
        result = ping(target, interface, count, 10, True)
        if result['received'] == count:
            return True

    return False


def print_journal_entries(start):
    print_head("Journal Entries")
    cmd = ('journalctl -q --no-pager '
           '-u systemd-networkd.service '
           '-u wpa_supplicant.service '
           ' -u netplan-* '
           '--since "{}" '.format(start.strftime('%Y-%m-%d %H:%M:%S')))
    print_cmd(cmd)
    sp.call(cmd, shell=True)


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

    start_time = datetime.datetime.now()

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
        print_journal_entries(start_time)
        raise SystemExit(1)
    time.sleep(20)

    print_head("Wait for interface to be routable")
    reached_routable = wait_for_routable(args.interface)

    test_result = False
    if reached_routable:
        print_head("Display address")
        print_address_info(args.interface)

        print_head("Display route table")
        print_route_info()

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
        print_journal_entries(start_time)
        raise SystemExit("ERROR: failed to apply restored config")

    if not test_result:
        print_journal_entries(start_time)
        raise SystemExit(1)

    print_journal_entries(start_time)


if __name__ == "__main__":
    # Check if executed with root
    if os.geteuid() != 0:
        raise SystemExit("Error: please run this command as root")
    main()
