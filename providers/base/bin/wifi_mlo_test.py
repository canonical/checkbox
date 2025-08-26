#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#  Zhongning Li <zhongning.li@canonical.com>

"""
This is a simple test to see if Wi-Fi MLO (Multi-Link Operation) is supported
on the DUT. 

Prerequisites for running this test:
- The environment variable MLO_SSID should be set in the launcher
  and passed in through argv
- The manifest entry "has_wifi_mlo" should be true 
"""

import subprocess as sp
import argparse
from sys import stderr
import itertools
import ctypes


COMMAND_TIMEOUT = 120


class nlattr(ctypes.Structure):
    _fields_ = [
        ("nla_len", ctypes.c_uint16),
        ("nla_type", ctypes.c_uint16),
    ]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--mlo-ssid",
        help="Name of the MLO wifi access point",
        dest="mlo_ssid",
    )
    return parser.parse_args()


def get_wifi_ssids() -> "list[str]":
    ssids = []  # type: list[str]
    nmcli_output = sp.check_output(
        ["nmcli", "-f", "SSID", "device", "wifi", "list", "--rescan", "yes"],
        universal_newlines=True,
    )
    for line in nmcli_output.splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue
        if clean_line in ("--", "SSID"):
            continue
        ssids.append(clean_line)

    return ssids


def get_wifi_interface() -> str:
    wifi_interface = None  # type: str | None
    nmcli_output = sp.check_output(
        [
            "nmcli",
            "--get-values",
            "GENERAL.DEVICE,GENERAL.TYPE",
            "device",
            "show",
        ],
        universal_newlines=True,
    )
    # https://stackoverflow.com/a/15358422
    name_type_pairs = [
        list(words_iterator)
        for is_separator, words_iterator in itertools.groupby(
            nmcli_output.splitlines(), lambda s: s == ""
        )
        if not is_separator
    ]

    for interface_name, interface_type in name_type_pairs:
        if interface_type == "wifi":
            wifi_interface = interface_name
            break

    if wifi_interface is None:
        print("There are no wifi interfaces on this DUT", file=stderr)
        exit(1)

    return wifi_interface


# def get_links_by_interface(wifi_interface: str) -> "list[str]":
#     """Returns a list of active link addresses associated with this interface

#     MLD with links:
#     - link ID  0 link addr 06:fe:8e:8a:8f:14
#     - link ID  2 link addr 4e:23:75:ef:d4:5a

#     This is a re-implementation of this small section in the kernel
#     https://git.kernel.org/pub/scm/linux/kernel/git/jberg/iw.git/tree/interface.c#n470
#     (...to avoid parsing the iw command)

#     :param wifi_interface: an interface name like wlp0s20f3 or wlan0
#     :return: number of links
#     """


def main():
    args = parse_args()
    print("Re-scanning available wifi APs...")
    all_wifi_ssids = get_wifi_ssids()

    if args.mlo_ssid not in all_wifi_ssids:
        print(
            'There\'s no WiFi AP named "{}".'.format(args.mlo_ssid),
            "Maybe it's too far from the DUT?",
            file=stderr,
        )
        exit(1)

    num_links = 0
    wifi_interface = get_wifi_interface()
    iw_output = sp.check_output(
        ["iw", "dev", wifi_interface, "info"], universal_newlines=True
    )

    if args.mlo_ssid not in iw_output:
        print(
            "Interface '{}' is not connected to SSID '{}'".format(
                wifi_interface, args.mlo_ssid
            )
        )
        exit(1)

    for line in iw_output.splitlines():
        clean_line = line.strip()
        if clean_line.startswith("- link ID"):
            num_links += 1

    if num_links < 2:
        print(
            "This wifi connection (interface: {}, ssid: {})".format(
                wifi_interface, args.mlo_ssid
            ),
            "is not an MLO connection.",
            "Expected at least 2 links, got {}".format(num_links),
            file=stderr,
        )
        exit(1)

    print(
        "OK! Found {} links in this connection".format(num_links),
        "(interface: {}, ssid: {})".format(wifi_interface, args.mlo_ssid),
    )


if __name__ == "__main__":
    main()
