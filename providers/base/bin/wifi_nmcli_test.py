#!/usr/bin/env python3
# Copyright 2017-2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Taihsiang Ho <taihsiang.ho@canonical.com>
#
# wireless connection tests using nmcli


import argparse
import datetime
import functools
import os
import subprocess as sp
import sys
import time

from distutils.version import LooseVersion
from gateway_ping_test import ping

print = functools.partial(print, flush=True)


def legacy_nmcli():
    cmd = "nmcli -v"
    output = sp.check_output(cmd, shell=True)
    version = LooseVersion(output.strip().split()[-1].decode())
    # check if using the 16.04 nmcli because of this bug
    # https://bugs.launchpad.net/plano/+bug/1896806
    if version < LooseVersion("1.9.9"):
        return True
    return False


def print_head(txt):
    print("##", txt)


def print_cmd(cmd):
    print("+", cmd)


def cleanup_nm_connections():
    print_head("Cleaning up NM connections")
    cmd = "nmcli -t -f TYPE,UUID,NAME c"
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    for line in output.decode(sys.stdout.encoding).splitlines():
        type, uuid, name = line.strip().split(':', 2)
        if type == '802-11-wireless':
            print("Deleting connection", name)
            cmd = "nmcli c delete {}".format(uuid)
            print_cmd(cmd)
            sp.call(cmd, shell=True)
    print()


def device_rescan():
    print_head("Calling a rescan")
    cmd = "nmcli d wifi rescan"
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        # Most often the rescan request fails because NM has itself started
        # a scan in recent past, we should let these operations complete before
        # attempting a connection
        print('Scan request failed, allow other operations to complete (15s)')
        time.sleep(15)
    print()


def list_aps(args):
    print_head("List APs")
    count = 0
    fields = "SSID,CHAN,FREQ,SIGNAL"
    cmd = "nmcli -t -f {} d wifi list ifname {}".format(
        fields, args.device)
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    for line in output.decode(sys.stdout.encoding).splitlines():
        # lp bug #1723372 - extra line in output on zesty
        if line.strip() == args.device:
            continue
        ssid, channel, frequency, signal = line.strip().rsplit(':', 3)
        print("SSID: {} Chan: {} Freq: {} Signal: {}".format(
            ssid, channel, frequency, signal))
        if hasattr(args, 'essid'):
            if ssid == args.essid:
                count += 1
        else:
            count += 1
    print()
    return count


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
    cmd = 'nmcli --mode tabular --terse --fields IP4.GATEWAY c show TEST_CON'
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    target = output.decode(sys.stdout.encoding).strip()
    print('Got gateway address: {}'.format(target))

    if target:
        count = 5
        result = ping(target, interface, count, 10, True)
        if result['received'] == count:
            return True

    return False


def wait_for_connected(interface, max_wait=5):
    connected = False
    attempts = 0
    while not connected and attempts < max_wait:
        cmd = "nmcli -m tabular -t -f GENERAL.STATE d show {}".format(
            args.device)
        print_cmd(cmd)
        output = sp.check_output(cmd, shell=True)
        state = output.decode(sys.stdout.encoding).strip()
        print(state)

        if state.startswith('100'):
            connected = True
            break
        time.sleep(1)
        attempts += 1
    if connected:
        print("Reached connected state")
    else:
        print("ERROR: did not reach connected state")
    print()
    return connected


def open_connection(args):
    # Configure the connection
    # ipv4.dhcp-timeout 30 : ensure plenty of time to get address
    # ipv6.method ignore : I believe that NM can report the device as Connected
    #                      if an IPv6 address is setup. This should ensure in
    #                      this test we are using IPv4
    print_head("Connection attempt")
    cmd = ("nmcli c add con-name TEST_CON "
           "ifname {} "
           "type wifi "
           "ssid {} "
           "-- "
           "ipv4.method auto "
           "ipv4.dhcp-timeout 30 "
           "ipv6.method ignore".format(args.device, args.essid))
    print_cmd(cmd)
    sp.call(cmd, shell=True)

    # Make sure the connection is brought up
    cmd = "nmcli c up TEST_CON"
    print_cmd(cmd)
    try:
        sp.call(cmd, shell=True, timeout=200 if legacy_nmcli() else None)
    except sp.TimeoutExpired:
        print("Connection activation failed\n")
    print()

    print_head("Ensure interface is connected")
    reached_connected = wait_for_connected(args.device)

    rc = 1
    if reached_connected:
        print_head("Display address")
        print_address_info(args.device)

        print_head("Display route table")
        print_route_info()

        print_head("Perform a ping test")
        test_result = perform_ping_test(args.device)
        if test_result:
            rc = 0
            print("Connection test passed\n")
        else:
            print("Connection test failed\n")
    return rc


def secured_connection(args):
    # Configure the connection
    # ipv4.dhcp-timeout 30 : ensure plenty of time to get address
    # ipv6.method ignore : I believe that NM can report the device as Connected
    #                      if an IPv6 address is setup. This should ensure in
    #                      this test we are using IPv4
    print_head("Connection attempt")
    cmd = ("nmcli c add con-name TEST_CON "
           "ifname {} "
           "type wifi "
           "ssid {} "
           "-- "
           "wifi-sec.key-mgmt wpa-psk "
           "wifi-sec.psk {} "
           "ipv4.method auto "
           "ipv4.dhcp-timeout 30 "
           "ipv6.method ignore".format(args.device, args.essid, args.psk))
    print_cmd(cmd)
    sp.call(cmd, shell=True)

    # Make sure the connection is brought up
    cmd = "nmcli c up TEST_CON"
    print_cmd(cmd)
    try:
        sp.call(cmd, shell=True, timeout=200 if legacy_nmcli() else None)
    except sp.TimeoutExpired:
        print("Connection activation failed\n")
    print()

    print_head("Ensure interface is connected")
    reached_connected = wait_for_connected(args.device)

    rc = 1
    if reached_connected:
        print_head("Display address")
        print_address_info(args.device)

        print_head("Display route table")
        print_route_info()

        print_head("Perform a ping test")
        test_result = perform_ping_test(args.device)
        if test_result:
            rc = 0
            print("Connection test passed\n")
        else:
            print("Connection test failed\n")
    return rc


def hotspot(args):
    print_head("Create Wi-Fi hotspot")
    cmd = ("nmcli c add type wifi ifname {} con-name TEST_CON autoconnect no"
           " ssid CHECKBOX_AP".format(args.device))
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        print("Connection creation failed\n")
        return retcode
    cmd = ("nmcli c modify TEST_CON 802-11-wireless.mode ap ipv4.method shared"
           " 802-11-wireless.band {}".format(args.band))
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        print("Set band failed\n")
        return retcode
    cmd = ("nmcli c modify TEST_CON wifi-sec.key-mgmt wpa-psk "
           "wifi-sec.psk \"ubuntu1234\"")
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        print("Setting up wifi security failed\n")
        return retcode
    cmd = "nmcli connection up TEST_CON"
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        print("Failed to bring up connection\n")
    print()
    return retcode


def print_journal_entries(start):
    print_head("Journal Entries")
    cmd = ('journalctl -q --no-pager '
           '-u snap.network-manager.networkmanager.service '
           '-u NetworkManager.service '
           '-u wpa_supplicant.service '
           '--since "{}" '.format(start.strftime('%Y-%m-%d %H:%M:%S')))
    print_cmd(cmd)
    sp.call(cmd, shell=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='WiFi connection test using mmcli')

    subparsers = parser.add_subparsers(dest='test_type')
    subparsers.required = True

    parser_scan = subparsers.add_parser(
        'scan', help='Test can scan for networks only')
    parser_scan.add_argument(
        'device', type=str, help='Device name e.g. wlan0')

    parser_open = subparsers.add_parser(
        'open', help='Test connection to an open access point')
    parser_open.add_argument(
        'device', type=str, help='Device name e.g. wlan0')
    parser_open.add_argument('essid', type=str, help='ESSID')
    parser_open.set_defaults(func=open_connection)

    parser_secured = subparsers.add_parser(
        'secured', help='Test connection to a secured access point')
    parser_secured.add_argument(
        'device', type=str, help='Device name e.g. wlan0')
    parser_secured.add_argument('essid', type=str, help='ESSID')
    parser_secured.add_argument('psk', type=str, help='Pre-Shared Key')
    parser_secured.set_defaults(func=secured_connection)

    parser_ap = subparsers.add_parser(
        'ap', help='Test creation of a hotspot')
    parser_ap.add_argument(
        'device', type=str, help='Device name e.g. wlan0')
    parser_ap.add_argument('band', type=str, help='Band')
    parser_ap.set_defaults(func=hotspot)

    args = parser.parse_args()

    start_time = datetime.datetime.now()

    cleanup_nm_connections()
    device_rescan()
    count = list_aps(args)

    if args.test_type == 'scan':
        if count == 0:
            print("Failed to find any APs")
            sys.exit(1)
        else:
            print("Found {} access points".format(count))
            sys.exit(0)

    if args.func:
        try:
            result = args.func(args)
        finally:
            cleanup_nm_connections()

    # The test is not required to run as root, but root access is required for
    # journal access so only attempt to print when e.g. running under Remote
    if result != 0 and os.geteuid() == 0:
        print_journal_entries(start_time)

    sys.exit(result)
