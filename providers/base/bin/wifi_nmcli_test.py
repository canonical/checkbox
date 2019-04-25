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
import functools
import subprocess as sp
import sys
import time

from distutils.version import LooseVersion


print = functools.partial(print, flush=True)


def print_head(txt):
    print("##", txt)


def print_cmd(cmd):
    print("+", cmd)


def legacy_nmcli():
    cmd = "nmcli -v"
    output = sp.check_output(cmd, shell=True)
    version = LooseVersion(output.strip().split()[-1].decode())
    # check if using an earlier nmcli version with different api
    # nmcli in trusty is 0.9.8.8
    if version < LooseVersion("0.9.9"):
        return True
    return False


def cleanup_nm_connections():
    print_head("Cleaning up NM connections")
    cmd = "nmcli -t -f TYPE,UUID,NAME c"
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    for line in output.decode(sys.stdout.encoding).splitlines():
        type, uuid, name = line.strip().split(':')
        if type == '802-11-wireless':
            print("Deleting connection", name)
            if legacy_nmcli():
                cmd = "nmcli c delete uuid {}".format(uuid)
            else:
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
    if legacy_nmcli():
        fields = "SSID,FREQ,SIGNAL"
        cmd = "nmcli -t -f {} d wifi list iface {}".format(fields, args.device)
    else:
        fields = "SSID,CHAN,FREQ,SIGNAL"
        cmd = "nmcli -t -f {} d wifi list ifname {}".format(
            fields, args.device)
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    for line in output.decode(sys.stdout.encoding).splitlines():
        # lp bug #1723372 - extra line in output on zesty
        if line.strip() == args.device:
            continue
        if legacy_nmcli():
            ssid, frequency, signal = line.strip().split(':')
            print("SSID: {} Freq: {} Signal: {}".format(
                ssid, frequency, signal))
        else:
            ssid, channel, frequency, signal = line.strip().split(':')
            print("SSID: {} Chan: {} Freq: {} Signal: {}".format(
                ssid, channel, frequency, signal))
        if hasattr(args, 'essid'):
            if ssid == args.essid:
                count += 1
        else:
            count += 1
    print()
    return count


def open_connection(args):
    print_head("Connection attempt")
    if legacy_nmcli():
        cmd = "nmcli d wifi connect {} iface {} name TEST_CON".format(
            args.essid, args.device)
    else:
        cmd = "nmcli d wifi connect {} ifname {} name TEST_CON".format(
            args.essid, args.device)
    print_cmd(cmd)
    sp.call(cmd, shell=True)
    if legacy_nmcli():
        cmd = ("nmcli -m tabular -t -f GENERAL d list | grep {} | "
               "awk -F: '{{print $15}}'".format(args.device))
    else:
        cmd = "nmcli -m tabular -t -f GENERAL.STATE d show {}".format(
            args.device)
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    state = output.decode(sys.stdout.encoding).strip()
    print(state)
    rc = 1
    if state.startswith('100'):
        rc = 0
    print()
    return rc


def secured_connection(args):
    print_head("Connection attempt")
    if legacy_nmcli():
        cmd = ("nmcli d wifi connect {} password {} iface {} name "
               "TEST_CON".format(args.essid, args.psk, args.device))
    else:
        cmd = ("nmcli d wifi connect {} password {} ifname {} name "
               "TEST_CON".format(args.essid, args.psk, args.device))
    print_cmd(cmd)
    sp.call(cmd, shell=True)
    if legacy_nmcli():
        cmd = ("nmcli -m tabular -t -f GENERAL d list | "
               "grep {} | awk -F: '{{print $15}}'".format(args.device))
    else:
        cmd = "nmcli -m tabular -t -f GENERAL.STATE d show {}".format(
            args.device)
    print_cmd(cmd)
    output = sp.check_output(cmd, shell=True)
    state = output.decode(sys.stdout.encoding).strip()
    print(state)
    rc = 1
    if state.startswith('100'):
        rc = 0
    print()
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
    cmd = "nmcli c modify TEST_CON wifi-sec.key-mgmt wpa-psk"
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        print("Set key-mgmt failed\n")
        return retcode
    cmd = "nmcli connection modify TEST_CON wifi-sec.psk \"ubuntu1234\""
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        print("Set PSK failed\n")
        return retcode
    cmd = "nmcli connection up TEST_CON"
    print_cmd(cmd)
    retcode = sp.call(cmd, shell=True)
    if retcode != 0:
        print("Failed to bring up connection\n")
    print()
    return retcode


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

    cleanup_nm_connections()
    if not legacy_nmcli():
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
            sys.exit(args.func(args))
        finally:
            cleanup_nm_connections()
