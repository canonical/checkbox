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
import shlex

from packaging import version as version_parser

from gateway_ping_test import ping


print = functools.partial(print, flush=True)


def legacy_nmcli():
    cmd = "nmcli -v"
    output = sp.check_output(shlex.split(cmd))
    version = version_parser.parse(output.strip().split()[-1].decode())
    # check if using the 16.04 nmcli because of this bug
    # https://bugs.launchpad.net/plano/+bug/1896806
    return version < version_parser.parse("1.9.9")


def print_head(txt):
    print("##", txt)


def print_cmd(cmd):
    print("+", cmd)


def _get_nm_wireless_connections():
    cmd = "nmcli -t -f TYPE,UUID,NAME,STATE connection"
    print_cmd(cmd)
    output = sp.check_output(shlex.split(cmd))
    connections = {}
    for line in output.decode(sys.stdout.encoding).splitlines():
        type, uuid, name, state = line.strip().split(":", 3)
        if type == "802-11-wireless":
            connections[name] = {"uuid": uuid, "state": state}
    return connections


def get_nm_activate_connection():
    print_head("Get NM activate connection name")
    connections = _get_nm_wireless_connections()
    for name, value in connections.items():
        state = value["state"]
        uuid = value["uuid"]
        if state == "activated":
            print("Activated Connection: {} {}".format(name, uuid))
            return uuid
    return ""


def turn_up_connection(uuid):
    # uuid can also be connection name
    print_head("Turn up NM connection")
    cmd = "nmcli c up {}".format(uuid)
    print("Turn up {}".format(uuid))
    activate_uuid = get_nm_activate_connection()
    if uuid == activate_uuid:
        print("{} state is already activated".format(uuid))
        return None
    try:
        print_cmd(cmd)
        sp.call(shlex.split(cmd))
    except Exception as e:
        print("Can't turn on {}: {}".format(uuid, str(e)))


def turn_down_nm_connections():
    print_head("Turn off NM all connections")
    connections = _get_nm_wireless_connections()
    for name, value in connections.items():
        uuid = value["uuid"]
        print("Turn down connection", name)
        try:
            cmd = "nmcli c down {}".format(uuid)
            print_cmd(cmd)
            sp.call(shlex.split(cmd))
            print("{} {} is down now".format(name, uuid))
        except Exception as e:
            print("Can't down {}: {}".format(uuid, str(e)))
    print()


def delete_test_ap_ssid_connection():
    print_head("Cleaning up TEST_CON connection")
    connections = _get_nm_wireless_connections()
    if "TEST_CON" not in connections:
        print("No TEST_CON connection found, nothing to delete")
        return
    try:
        cmd = "nmcli c delete TEST_CON"
        print_cmd(cmd)
        sp.call(shlex.split(cmd))
        print("TEST_CON is deleted")
    except Exception as e:
        print("Can't delete TEST_CON : {}".format(str(e)))


def device_rescan():
    print_head("Calling a rescan")
    cmd = "nmcli d wifi rescan"
    print_cmd(cmd)
    retcode = sp.call(shlex.split(cmd))
    if retcode != 0:
        # Most often the rescan request fails because NM has itself started
        # a scan in recent past, we should let these operations complete before
        # attempting a connection
        print("Scan request failed, allow other operations to complete (15s)")
        time.sleep(15)
    print()


def list_aps(ifname, essid=None):
    if essid:
        print_head("List APs with ESSID: {}".format(essid))
    else:
        print("List all APs")
    aps_dict = {}
    fields = "SSID,CHAN,FREQ,SIGNAL"
    cmd = "nmcli -t -f {} d wifi list ifname {}".format(fields, ifname)
    output = sp.check_output(shlex.split(cmd))
    for line in output.decode(sys.stdout.encoding).splitlines():
        # lp bug #1723372 - extra line in output on zesty
        if line.strip() == ifname:  # Skip device name line
            continue
        ssid, channel, frequency, signal = line.strip().rsplit(":", 3)
        if essid and ssid != essid:
            continue
        aps_dict[ssid] = {"Chan": channel, "Freq": frequency, "Signal": signal}
    return aps_dict


def show_aps(aps_dict):
    for ssid, values in aps_dict.items():
        print(
            "SSID: {} Chan: {} Freq: {} Signal: {}".format(
                ssid, values["Chan"], values["Freq"], values["Signal"]
            )
        )
    print()


def print_address_info(interface):
    cmd = "ip address show dev {}".format(interface)
    print_cmd(cmd)
    sp.call(shlex.split(cmd))
    print()


def print_route_info():
    cmd = "ip route"
    print_cmd(cmd)
    sp.call(shlex.split(cmd))
    print()


def perform_ping_test(interface):
    target = None
    cmd = "nmcli --mode tabular --terse --fields IP4.GATEWAY c show TEST_CON"
    print_cmd(cmd)
    output = sp.check_output(shlex.split(cmd))
    target = output.decode(sys.stdout.encoding).strip()
    print("Got gateway address: {}".format(target))

    if target:
        count = 5
        result = ping(target, interface, count, 10)
        if result["received"] == count:
            return True

    return False


def wait_for_connected(interface, essid, max_wait=5):
    connected = False
    attempts = 0
    while not connected and attempts < max_wait:
        cmd = (
            "nmcli -m tabular -t -f GENERAL.STATE,GENERAL.CONNECTION "
            "d show {}".format(interface)
        )
        print_cmd(cmd)
        output = sp.check_output(shlex.split(cmd))
        state, ssid = output.decode(sys.stdout.encoding).strip().splitlines()

        if state.startswith("100") and ssid == essid:
            connected = True
            break

        time.sleep(1)
        attempts += 1

    if connected:
        print("Reached connected state with ESSID: {}".format(essid))
    else:
        print(
            "ERROR: did not reach connected state with ESSID: {}".format(essid)
        )
        if ssid != essid:
            print(
                "ESSID mismatch:\n  Excepted:{}\n  Actually:{}".format(
                    ssid, essid
                )
            )
        if not state.startswith("100"):
            print("State is not connected: {}".format(state))

    print()
    return connected


def open_connection(args):
    # Configure the connection
    # ipv4.dhcp-timeout 30 : ensure plenty of time to get address
    # ipv6.method ignore : I believe that NM can report the device as Connected
    #                      if an IPv6 address is setup. This should ensure in
    #                      this test we are using IPv4
    print_head("Connection attempt")
    cmd = (
        "nmcli c add con-name TEST_CON "
        "ifname {} "
        "type wifi "
        "ssid '{}' "
        "-- "
        "ipv4.method auto "
        "ipv4.dhcp-timeout 30 "
        "ipv6.method ignore".format(args.device, args.essid)
    )
    print_cmd(cmd)
    sp.call(shlex.split(cmd))

    # Make sure the connection is brought up
    turn_up_connection("TEST_CON")

    print_head("Ensure interface is connected")
    reached_connected = wait_for_connected(args.device, "TEST_CON")

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
    cmd = (
        "nmcli c add con-name TEST_CON "
        "ifname {} "
        "type wifi "
        "ssid '{}' "
        "-- "
        "wifi-sec.key-mgmt {} "
        "wifi-sec.psk {} "
        "ipv4.method auto "
        "ipv4.dhcp-timeout 30 "
        "ipv6.method ignore".format(
            args.device, args.essid, args.exchange, args.psk
        )
    )
    print_cmd(cmd)
    sp.call(shlex.split(cmd))

    # Make sure the connection is brought up
    turn_up_connection("TEST_CON")

    print_head("Ensure interface is connected")
    reached_connected = wait_for_connected(args.device, "TEST_CON")

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
    cmd = (
        "nmcli c add type wifi ifname {} con-name TEST_CON autoconnect no"
        " ssid CHECKBOX_AP".format(args.device)
    )
    print_cmd(cmd)
    retcode = sp.call(shlex.split(cmd))
    if retcode != 0:
        print("Connection creation failed\n")
        return retcode
    cmd = (
        "nmcli c modify TEST_CON 802-11-wireless.mode ap ipv4.method shared"
        " 802-11-wireless.band {}".format(args.band)
    )
    print_cmd(cmd)
    retcode = sp.call(shlex.split(cmd))
    if retcode != 0:
        print("Set band failed\n")
        return retcode
    cmd = (
        "nmcli c modify TEST_CON wifi-sec.key-mgmt wpa-psk "
        'wifi-sec.psk "ubuntu1234"'
    )
    print_cmd(cmd)
    retcode = sp.call(shlex.split(cmd))
    if retcode != 0:
        print("Setting up wifi security failed\n")
        return retcode
    turn_up_connection("TEST_CON")
    if retcode != 0:
        print("Failed to bring up connection\n")
    print()
    return retcode


def print_journal_entries(start):
    print_head("Journal Entries")
    cmd = (
        "journalctl -q --no-pager "
        "-u snap.network-manager.networkmanager.service "
        "-u NetworkManager.service "
        "-u wpa_supplicant.service "
        '--since "{}" '.format(start.strftime("%Y-%m-%d %H:%M:%S"))
    )
    print_cmd(cmd)
    sp.call(shlex.split(cmd))


def parser_args():
    parser = argparse.ArgumentParser(
        description="WiFi connection test using mmcli"
    )

    subparsers = parser.add_subparsers(dest="test_type")
    subparsers.required = True

    parser_scan = subparsers.add_parser(
        "scan", help="Test can scan for networks only"
    )
    parser_scan.add_argument("device", type=str, help="Device name e.g. wlan0")

    parser_open = subparsers.add_parser(
        "open", help="Test connection to an open access point"
    )
    parser_open.add_argument("device", type=str, help="Device name e.g. wlan0")
    parser_open.add_argument("essid", type=str, help="ESSID")
    parser_open.set_defaults(func=open_connection)

    parser_secured = subparsers.add_parser(
        "secured", help="Test connection to a secured access point"
    )
    parser_secured.add_argument(
        "device", type=str, help="Device name e.g. wlan0"
    )
    parser_secured.add_argument("essid", type=str, help="ESSID")
    parser_secured.add_argument("psk", type=str, help="Pre-Shared Key")
    parser_secured.add_argument(
        "--exchange",
        type=str,
        default="wpa-psk",
        help="exchange type (default: %(default)s)",
    )
    parser_secured.set_defaults(func=secured_connection)

    parser_ap = subparsers.add_parser("ap", help="Test creation of a hotspot")
    parser_ap.add_argument("device", type=str, help="Device name e.g. wlan0")
    parser_ap.add_argument("band", type=str, help="Band")
    parser_ap.set_defaults(func=hotspot)

    args = parser.parse_args()

    return args


def main():
    args = parser_args()
    start_time = datetime.datetime.now()
    device_rescan()
    essid = getattr(args, "essid", None)
    aps_dict = list_aps(args.device, essid)
    show_aps(aps_dict)

    if args.test_type == "scan":
        if not aps_dict:
            print("Failed to find any APs")
            return 1
        else:
            print("Found {} access points".format(len(aps_dict)))
            return 0

    if not aps_dict:
        print("Targed access points: {} not found".format(args.essid))
        return 1

    if args.func:
        delete_test_ap_ssid_connection()
        activated_uuid = get_nm_activate_connection()
        turn_down_nm_connections()
        try:
            result = args.func(args)
        finally:
            turn_up_connection(activated_uuid)
            delete_test_ap_ssid_connection()

    # The test is not required to run as root, but root access is required for
    # journal access so only attempt to print when e.g. running under Remote
    if result != 0 and os.geteuid() == 0:
        print_journal_entries(start_time)
    return result


if __name__ == "__main__":
    sys.exit(main())
