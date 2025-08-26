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

import argparse
import itertools
import subprocess as sp
from sys import stderr

from checkbox_support.helpers.retry import retry

COMMAND_TIMEOUT = 120


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--mlo-ssid",
        help="Name of the open (password-less) MLO wifi access point",
        dest="mlo_ssid",
        required=True,
        type=str,
    )
    return parser.parse_args()


@retry(5, 30)
def connect(ssid: str):
    nmcli_output = sp.check_output(
        ["nmcli", "-f", "SSID", "device", "wifi", "list", "--rescan", "yes"],
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT,
    )

    for line in nmcli_output.splitlines():
        clean_line = line.strip()
        if ssid == clean_line:
            # should match exactly, otherwise the nmcli connect is
            # guaranteed to fail
            sp.check_call(["nmcli", "device", "wifi", "connect", ssid])
            print("OK! Connected to {}".format(ssid))
            break


@retry(5, 30)
def disconnect(ssid: str):
    sp.check_call(
        ["nmcli", "connection", "delete", ssid],
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT,
    )


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
        timeout=COMMAND_TIMEOUT,
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


def main():
    args = parse_args()
    ssid = args.mlo_ssid
    wifi_interface = get_wifi_interface()

    print("Attempting to connect to {}...".format(ssid))
    connect(ssid)

    num_links = 0
    iw_output = sp.check_output(
        ["iw", "dev", wifi_interface, "info"],
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT,
    )
    # already have all the outputs we need, disconnect first
    disconnect(ssid)

    if args.mlo_ssid not in iw_output:
        print(
            "Interface '{}' is not connected to SSID '{}'".format(
                wifi_interface, args.mlo_ssid
            )
        )
        exit(1)

    # https://git.kernel.org/pub/scm/linux/kernel/git/jberg/iw.git/tree/interface.c#n480
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
