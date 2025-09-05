#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#  Zhongning Li <zhongning.li@canonical.com>

"""
This is a simple test to see if Wi-Fi MLO (Multi-Link Operation) is supported
on the DUT.

The checks come from this guide:
https://documentation.meraki.com/MR/Wi-Fi_Basics_and_Best_Practices/Wi-Fi_7_(802.11be)_Technical_Guide

Prerequisites for running this test:
- 6.14+ kernel (24.04.3 is ok!)
- wpasupplicant >= 2.11
- The environment variable MLO_SSID should be set in the launcher
  and passed in through argv
- The manifest entry "has_wifi_mlo" should be true
"""

import argparse
import itertools
import subprocess as sp
import typing as T
from sys import stderr

from checkbox_support.helpers.retry import retry

COMMAND_TIMEOUT = 120


def remove_prefix(s: str, prefix: str) -> str:
    """3.8 and older doesn't have <str>.removeprefix()"""
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def remove_suffix(s: str, suffix: str) -> str:
    """3.8 and older doesn't have <str>.removesuffix()"""
    if s.endswith(suffix):
        return s[: len(s) - len(suffix)]
    return s


class ConnectionInfo:
    # ideally we don't parse iw but reimplementing the
    # whole connect -> bind -> link sequence is even more complicated
    def __init__(
        self,
        mcs: int,
        conn_type: "T.Literal['EHT', 'HE', 'VT', 'HT']",
        direction: "T.Literal['rx', 'tx']",
        bandwidth: int,
    ) -> None:
        # TODO: Move to dataclass once we drop 3.5
        self.mcs = mcs
        self.conn_type = conn_type
        self.direction = direction
        self.bandwidth = bandwidth

    @classmethod
    def parse(
        cls, iw_link_output: str
    ) -> "tuple[ConnectionInfo | None, ConnectionInfo | None]":
        """Parses the output of 'iw dev <interface> link' and put the values in
        this wrapper object

        Check this file to see how the outputs are produced by iw:
        https://git.kernel.org/pub/scm/linux/kernel/git/jberg/iw.git/tree/station.c#n199 # noqa: E501

        For MCS (Modulation Coding Scheme) values, check this table:
        https://mcsindex.net/

        :param iw_link_output: output from iw dev <interface> link
        :return: the (tx, rx) pair
        """
        tx = None  # type: ConnectionInfo | None
        rx = None  # type: ConnectionInfo | None

        for line in iw_link_output.splitlines():
            clean_line = line.strip()
            if not clean_line.startswith(("tx bitrate", "rx bitrate")):
                continue

            is_tx = clean_line.startswith("tx")
            words = remove_prefix(
                remove_prefix(clean_line, "tx bitrate"), "rx bitrate"
            ).split()
            # words = [48, MBit/s, 320MHz, EHT-MCS, 11, EHT-NSS, 2, EHT-GI, 0]

            conn_type = remove_suffix(words[3], "-MCS")
            assert conn_type in (
                "EHT",  # wifi 7
                "HE",  # wifi 6 and wifi 6e
                "VT",  # wifi 5
                "HT",  # wifi 4
            ), "Unexpected connection type {}".format(conn_type)

            if is_tx:
                tx = ConnectionInfo(
                    int(words[4]),
                    conn_type,
                    "tx",
                    int(remove_suffix(words[2], "MHz")),
                )
            else:
                rx = ConnectionInfo(
                    int(words[4]),
                    conn_type,
                    "rx",
                    int(remove_suffix(words[2], "MHz")),
                )

        return (tx, rx)


def get_num_mlo_links(iw_info_output: str) -> int:
    """Get the number of MLO links based on the output of 'iw dev <iface> info'

    :param iw_info_output: 'iw dev <iface> info's output
    :return: number of MLO links. This is NOT the same as regular wifi links
    """
    # https://git.kernel.org/pub/scm/linux/kernel/git/jberg/iw.git/tree/interface.c#n480 # noqa: E501

    num_links = 0
    for line in iw_info_output.splitlines():
        if line.strip().startswith("- link ID"):
            num_links += 1

    return num_links


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--mlo-ssid",
        help="Name/SSID of the MLO wifi access point",
        dest="mlo_ssid",
        required=True,
        type=str,
    )
    parser.add_argument(
        "-p", "--password", help="the password to use when connecting to wifi"
    )
    return parser.parse_args()


@retry(5, 30)
def connect(ssid: str, password: "str | None"):
    # delete the connection if we have it
    print("Deleting existing connections related to {}".format(ssid))
    sp.run(["nmcli", "connection", "delete", ssid])

    # color is removed when nmcli detects its output is being piped
    # so we don't need to manually remove colors
    nmcli_output = sp.check_output(
        [
            "nmcli",
            "-get-values",
            "SSID",
            "device",
            "wifi",
            "list",
            "--rescan",
            "yes",
        ],
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT,
    )

    for line in nmcli_output.splitlines():
        clean_line = line.strip()
        if ssid == clean_line:
            # should match exactly, otherwise the nmcli connect is
            # guaranteed to fail
            print("Connecting to", ssid)
            if password:
                sp.check_call(
                    [
                        "nmcli",
                        "device",
                        "wifi",
                        "connect",
                        ssid,
                        "password",
                        password,
                    ]
                )
            else:
                sp.check_call(["nmcli", "device", "wifi", "connect", ssid])
            print("OK! Connected to {}".format(ssid))
            break

    raise RuntimeError("Did not see {} in nmcli's scan output".format(ssid))


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
            "-get-values",
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
            break  # just pick the first one

    if wifi_interface is None:
        raise SystemExit("There are no wifi interfaces on this DUT")

    return wifi_interface


def main():
    args = parse_args()
    ssid = args.mlo_ssid
    wifi_interface = get_wifi_interface()

    print("Attempting to connect to {}...".format(ssid))
    connect(ssid, args.password)

    iw_info_output = sp.check_output(
        ["iw", "dev", wifi_interface, "info"],
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT,
    )
    iw_link_output = sp.check_output(
        ["iw", "dev", wifi_interface, "link"],
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT,
    )

    # already have all the outputs we need, disconnect first
    disconnect(ssid)

    if args.mlo_ssid not in iw_info_output:
        raise SystemExit(
            "Interface '{}' was not connected to SSID '{}'".format(
                wifi_interface, args.mlo_ssid
            )
        )

    num_links = get_num_mlo_links(iw_info_output)
    (tx, rx) = ConnectionInfo.parse(iw_link_output)

    if (tx and tx.bandwidth == 320) or (rx and rx.bandwidth == 320):
        print("OK! This connection is using 320mHz bandwidth")
    else:
        raise SystemExit(
            "This wifi connection (interface: {}, ssid: {}) ".format(
                wifi_interface, args.mlo_ssid
            )
            + "is not using 320mHz bandwidth. "
            + "It's possible that the AP of {} isn't configured correctly".format(
                args.mlo_ssid
            )
        )

    if (tx and tx.conn_type == "EHT") or (rx and rx.conn_type == "EHT"):
        print("OK! This is a wifi 7 connection (EHT)")
    else:
        raise SystemExit(
            "This wifi connection (interface: {}, ssid: {}) ".format(
                wifi_interface, args.mlo_ssid
            )
            + "is not a wifi 7 connection. "
            + "Expected EHT, but got tx: {} rx: {}".format(
                tx and tx.conn_type, rx and rx.conn_type
            )
        )

    if (tx and tx.mcs in (12, 13)) or (rx and rx.mcs in (12, 13)):
        print("OK! This connection is using 4096 QAM (MCS 12 and 13)!")
    else:
        # DUT pretty much has to be next to the AP for this
        print(
            "Expected 4096QAM (MCS12 13), but got tx MCS: {} rx MCS:{}".format(
                tx and tx.mcs, rx and rx.mcs
            ),
            "Which MCS is chosen by the AP is highly dependent on the environment,",
            "Try moving the DUT next to the AP and run the test again.",
            file=stderr,
        )

    if num_links >= 2:
        print(
            "OK! Found {} links in this connection".format(num_links),
            "(interface: {}, ssid: {})".format(wifi_interface, args.mlo_ssid),
        )
    else:
        raise SystemExit(
            "This wifi connection (interface: {}, ssid: {}) ".format(
                wifi_interface, args.mlo_ssid
            )
            + "is not an MLO connection. "
            + "Expected at least 2 MLO links, got {}".format(num_links),
            # mlo link != plain wifi link, it;s possible to get 0 here
        )


if __name__ == "__main__":
    main()
