#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

import configparser
import os
import subprocess as sp
import sys


def check_networkmanager(interface, expected_address):
    def nmcli_field(cmd):
        val = (
            sp.check_output(cmd)
            .decode(sys.stdout.encoding)
            .strip()
            .split(":")[1]
        )
        return val

    carrier = nmcli_field(
        [
            "nmcli",
            "-t",
            "--fields",
            "WIRED-PROPERTIES.CARRIER",
            "d",
            "show",
            interface,
        ]
    )
    if carrier == "off":
        raise SystemExit("ERROR: No cable present")

    conn_name = nmcli_field(
        [
            "nmcli",
            "-t",
            "--fields",
            "GENERAL.CONNECTION",
            "d",
            "show",
            interface,
        ]
    )
    if conn_name == "--":
        raise SystemExit(f"ERROR: No connection active on {interface}")
    print(f"Connection active on {interface} is {conn_name}")

    conn_method = nmcli_field(
        ["nmcli", "-t", "--fields", "ipv4.method", "c", "show", conn_name]
    )
    if conn_method == "auto":
        raise SystemExit(f"FAIL: connection method {conn_method}")

    address = nmcli_field(
        ["nmcli", "-t", "--fields", "IP4.ADDRESS", "c", "show", conn_name]
    )
    print(f"Found static address: {address}")
    if expected_address:
        if expected_address != address:
            raise SystemExit("FAIL: address doesn't match")


def check_networkd(interface, expected_address):
    config_f = f"/run/systemd/network/10-netplan-{interface}.network"
    if not os.path.exists(config_f):
        raise SystemExit(
            f"ERROR: expected config file does not exist {config_f}"
        )

    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(config_f)

    if "Network" not in parser.sections():
        raise SystemExit('ERROR: no section "Network" found in config file ')

    if "DHCP" in parser["Network"]:
        if parser["Network"]["DHCP"] in ("true", "ipv4", "ipv6"):
            raise SystemExit("FAIL: interface configured for DHCP")

    if "Address" in parser["Network"]:
        print("Found static address: {}".format(parser["Network"]["Address"]))
        if expected_address:
            if expected_address != parser["Network"]["Address"]:
                raise SystemExit("FAIL: address doesn't match")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("USAGE: check_static.py [manager] [interface]")
    manager = sys.argv[1]
    interface = sys.argv[2]

    if not os.path.exists(f"/sys/class/net/{interface}"):
        raise SystemExit(f"ERROR: {interface} doesn't exist")

    configuration_key = f"STATIC_IP_{interface.upper()}"
    expected_address = os.environ.get(configuration_key)
    if expected_address:
        print(
            "Testing for expected address: {}={}\n".format(
                configuration_key, expected_address
            )
        )
    else:
        print("No expected address specified, testing for non-DHCP only")
        print(f"Set key {configuration_key} for address check\n")

    if manager == "nm":
        check_networkmanager(interface, expected_address)
    elif manager == "networkd":
        check_networkd(interface, expected_address)

    print("PASS")


if __name__ == "__main__":
    main()
