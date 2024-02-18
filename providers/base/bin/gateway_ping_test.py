#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2007-2024 Canonical Ltd.
# Written by:
#   Brendan Donegan <brendan.donegan@canonical.com>
#   Daniel Manrique <daniel.manrique@canonical.com>
#   David Murphy <david.murphy@canonical.com>
#   Javier Collado <javier.collado@canonical.com>
#   Jeff Lane <jeffrey.lane@canonical.com>
#   Marc Tardif <marc.tardif@canonical.com>
#   Mathieu Trudel-Lapierre <mathieu.trudel-lapierre@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Massimiliano Girardi <massimiliano.giarardi@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

from gettext import gettext as _
import argparse
import gettext
import logging
import os
import re
import socket
import struct
import subprocess
import sys
import time

from contextlib import suppress
from typing import Dict


class Route:
    """
    Gets routing information from the system.
    """

    def __init__(self, interface):
        self.interface = interface

    def _num_to_dotted_quad(self, number):
        """
        Convert long int to dotted quad string
        """
        return socket.inet_ntoa(struct.pack("<L", number))

    def _get_default_gateway_from_ip(self):
        try:
            # Note: this uses -o instead of -j for xenial/bionic compatibility
            routes = subprocess.check_output(
                [
                    "ip",
                    "-o",
                    "route",
                    "show",
                    "default",
                    "0.0.0.0/0",
                    "dev",
                    self.interface,
                ],
                universal_newlines=True,
            )
        except subprocess.CalledProcessError:
            return None
        for route in routes.splitlines():
            if route.startswith("default via"):
                return route.split()[2]
        return None

    def _get_default_gateway_from_proc(self):
        """
        Returns the current default gateway, reading that from /proc
        """
        logging.debug(_("Reading default gateway information from /proc"))
        try:
            with open("/proc/net/route", "rt") as stream:
                route = stream.read()
        except Exception:
            logging.error(_("Failed to read def gateway from /proc"))
            return None

        proc_table_re = re.compile(
            r"\n(?P<interface>\w+)\s+00000000\s+" r"(?P<def_gateway>[\w]+)\s+"
        )
        proc_table_lines = proc_table_re.finditer(route)
        for proc_table_line in proc_table_lines:
            def_gateway = proc_table_line.group("def_gateway")
            interface = proc_table_line.group("interface")
            if interface == self.interface and def_gateway:
                return self._num_to_dotted_quad(int(def_gateway, 16))
        logging.error(_("Could not find def gateway info in /proc"))
        return None

    def _get_default_gateway_from_bin_route(self):
        """
        Return the gateway for the interface associated with this Route object.
        """
        default_gws = get_default_gateways()
        return default_gws.get(self.interface)

    def _get_ip_addr_info(self):
        return subprocess.check_output(
            ["ip", "-o", "addr", "show"], universal_newlines=True
        )

    def get_broadcast(self):
        # Get list of all IPs from all my interfaces,
        ip_addr_infos = self._get_ip_addr_info()
        for addr_info_line in ip_addr_infos.splitlines():
            # id: if_name inet addr/mask brd broadcast
            addr_info_fields = addr_info_line.split()
            with suppress(IndexError):
                if (
                    addr_info_fields[1] == self.interface
                    and addr_info_fields[4] == "brd"
                ):
                    return addr_info_fields[5]
        raise ValueError(
            "Unable to determine broadcast for iface {}".format(self.interface)
        )

    def _get_default_gateway_from_networkctl(self):
        try:
            network_info = subprocess.check_output(
                [
                    "networkctl",
                    "status",
                    "--no-pager",
                    "--no-legend",
                    self.interface,
                ],
                universal_newlines=True,
            )
        except subprocess.CalledProcessError:
            return None
        for line in network_info.splitlines():
            line = line.strip()
            if line.startswith("Gateway:"):
                return line.split()[-1]
        return None

    def get_default_gateways(self) -> set:
        """
        Use multiple sources to get the default gateway to be robust to
        possible platform bugs
        """
        def_gateways = {
            self._get_default_gateway_from_ip(),
            self._get_default_gateway_from_proc(),
            self._get_default_gateway_from_bin_route(),
            self._get_default_gateway_from_networkctl(),
        }
        def_gateways -= {None}
        if len(def_gateways) > 1:
            logging.warning(
                "Found more than one default gateway for interface {}".format(
                    self.interface
                )
            )
        return def_gateways

    @staticmethod
    def get_interface_from_ip(ip):
        # Note: this uses -o instead of -j for xenial/bionic compatibility
        route_info = subprocess.check_output(
            ["ip", "-o", "route", "get", ip], universal_newlines=True
        )
        for line in route_info.splitlines():
            # ip dev device_name src ...
            fields = line.split()
            if len(fields) > 3:
                return fields[2]
        raise ValueError(
            "Unable to determine any device used for {}".format(ip)
        )

    @staticmethod
    def get_any_interface():
        # Note: this uses -o instead of -j for xenial/bionic compatibility
        route_infos = subprocess.check_output(
            ["ip", "-o", "route", "show", "default", "0.0.0.0/0"],
            universal_newlines=True,
        )
        for route_info in route_infos.splitlines():
            route_info_fields = route_info.split()
            if len(route_info_fields) > 5:
                return route_info_fields[4]
        raise ValueError("Unable to determine any valid interface")

    @staticmethod
    def from_ip(ip: str):
        """
        Build an instance of Route given an ip, if no ip is provided the best
        interface that can route to 0.0.0.0/0 is selected (as described by
        metric)
        """
        if ip:
            interface = Route.get_interface_from_ip(ip)
            return Route(interface)
        return Route(Route.get_any_interface())


def is_reachable(ip, interface):
    """
    Ping an ip to see if it is reachable
    """
    result = ping(ip, interface)
    return result["transmitted"] >= result["received"] > 0


def get_default_gateway_reachable_on(interface: str) -> str:
    """
    Returns the default gateway of an interface if it is reachable
    """
    if not interface:
        raise ValueError("Unable to ping on interface None")
    route = Route(interface=interface)
    desired_targets = route.get_default_gateways()
    for desired_target in desired_targets:
        if is_reachable(desired_target, interface):
            return desired_target
    raise ValueError(
        "Unable to reach any estimated gateway of interface {}".format(
            interface
        ),
    )


def get_any_host_reachable_on(interface: str) -> str:
    """
    Returns any host that it can reach from a given interface
    """
    if not interface:
        raise ValueError("Unable to ping on interface None")
    route = Route(interface=interface)
    broadcast = route.get_broadcast()
    arp_parser_re = re.compile(
        r"\? \((?P<ip>[\d.]+)\) at (?P<mac>[a-f0-9\:]+) "
        r"\[ether\] on (?P<iface>[\w\d]+)"
    )
    # retry a few times to get something in the arp table
    for i in range(10):
        ping(broadcast, interface, broadcast=True)
        # Get output from arp -a -n to get known IPs
        arp_table = subprocess.check_output(
            ["arp", "-a", "-n"], universal_newlines=True
        )
        hosts_in_arp_table = [
            arp_entry.group("ip")  # ip
            for arp_entry in arp_parser_re.finditer(arp_table)
            if arp_entry.group("iface") == interface
        ]
        # we don't know how an ip got in the arp table, lets try to reach them
        # and return the first that we can acutally reach
        for host in hosts_in_arp_table:
            if is_reachable(host, interface):
                return host
        # we were unable to get any reachable host in the arp table, this may
        # be due to a slow network, lets retry in a few seconds
        time.sleep(5)
    raise ValueError(
        "Unable to reach any host on interface {}".format(interface)
    )


def get_host_to_ping(interface: str, target: str = None) -> "str|None":
    """
    Attempts to determine a reachable host to ping on the specified network
    interface. First it tries to ping the provided target. If no target is
    specified or the target is not reachable, it then attempts to find a
    reachable host by trying the default gateway and finally falling back on
    any host on the network interface.

    @returns: The reachable host if any, else None
    """
    # Try to use the provided target if it is reachable
    if target and is_reachable(target, interface):
        return target
    # From here onward, lets try to estimate a reachable target
    if not interface:
        route = Route.from_ip(target)
        interface = route.interface

    # Try first with any default gateway that we can gather on the interface
    with suppress(ValueError):
        return get_default_gateway_reachable_on(interface)

    # Try with any host we can find reachable on the interface
    with suppress(ValueError):
        return get_any_host_reachable_on(interface)

    # Unable to estimate any host to reach
    return None


def ping(
    host: str,
    interface: "str|None",
    broadcast=False,
):
    """
    pings an host via an interface count times within the given deadline.
    If the interface is None, it will not be used.
    If the host is a broadcast host, use the broadcast kwarg

    @returns: on success the stats of the ping "transmitted", "received" and
              "pct_loss"
    @returns: on failure a dict with a "cause" key, with the failure reason
    """
    command = ["ping", str(host), "-c", "2", "-w", "4"]
    if interface:
        command.append("-I{}".format(interface))
    if broadcast:
        command.append("-b")
    reg = re.compile(
        r"(\d+) packets transmitted, (\d+) received,"
        r".*([0-9]*\.?[0-9]*.)% packet loss"
    )
    ping_summary = {"transmitted": 0, "received": 0, "pct_loss": 0}
    try:
        output = subprocess.check_output(
            command, universal_newlines=True, stderr=subprocess.PIPE
        )
    except (OSError, FileNotFoundError) as e:
        ping_summary["cause"] = str(e)
        return ping_summary
    except subprocess.CalledProcessError as e:
        # Ping returned fail exit code
        # broadcast will always do so
        if broadcast:
            return
        ping_summary[
            "cause"
        ] = "Failed with exception: {}\nstdout: {}\nstderr: {}".format(
            str(e), e.stdout, e.stderr
        )
        return ping_summary

    print(output)
    try:
        received = next(re.finditer(reg, output))
        ping_summary = {
            "transmitted": int(received.group(1)),
            "received": int(received.group(2)),
            "pct_loss": int(received.group(3)),
        }
    except StopIteration:
        ping_summary[
            "cause"
        ] = "Failed to parse the stats from the ping output. Log: {}".format(
            output
        )
    return ping_summary


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "host",
        nargs="?",
        default=None,
        help=_("host to ping"),
    )
    iface_mutex_group = parser.add_mutually_exclusive_group()
    iface_mutex_group.add_argument(
        "-I",
        "--interface",
        help=_("use specified interface to send packets"),
        action="append",
        dest="interfaces",
        default=[None],
    )
    iface_mutex_group.add_argument(
        "--any-cable-interface",
        help=_("use any cable interface to send packets"),
        action="store_true",
    )
    return parser.parse_args(argv)


def main(argv) -> int:
    gettext.textdomain("com.canonical.certification.checkbox")
    gettext.bindtextdomain(
        "com.canonical.certification.checkbox",
        os.getenv("CHECKBOX_PROVIDER_LOCALE_DIR", None),
    )

    args = parse_args(argv)

    if args.any_cable_interface:
        print(_("Looking for all cable interfaces..."))
        all_ifaces = get_default_gateways().keys()
        args.interfaces = list(filter(is_cable_interface, all_ifaces))

    # If given host is not pingable, override with something pingable.
    host = get_host_to_ping(interface=args.interfaces[0], target=args.host)

    print(_("Checking connectivity to {0}").format(host))

    if host:
        ping_summary = ping(host, args.interfaces[0])
    else:
        ping_summary = {
            "received": 0,
            "cause": "Unable to find any host to ping",
        }

    if ping_summary["received"] == 0:
        print(_("FAIL: All packet loss."))
        if ping_summary.get("cause"):
            print("Possible cause: {}".format(ping_summary["cause"]))
        return 1
    elif ping_summary["transmitted"] != ping_summary["received"]:
        print(_("FAIL: {0}% packet loss.").format(ping_summary["pct_loss"]))
        return 1
    else:
        print(_("PASS: 0% packet loss").format(host))
        return 0


def get_default_gateways() -> Dict[str, str]:
    """
    Use `route` program to find default gateways for all interfaces.

    returns a dictionary in a form of {interface_name: gateway}
    """
    try:
        routes = subprocess.check_output(
            ["route", "-n"], universal_newlines=True
        )
    except subprocess.CalledProcessError as exc:
        logging.debug("Failed to run `route -n `", exc)
        return {}
    regex = r"^0\.0\.0\.0\s+(?P<gw>[\w.]+)\s.*\s(?P<interface>[\w.]+)$"
    matches = re.finditer(regex, routes, re.MULTILINE)

    return {m.group("interface"): m.group("gw") for m in matches}


def is_cable_interface(interface: str) -> bool:
    """
    Check if the interface is a cable interface.
    This is a simple heuristic that checks if the interface is named
    "enX" or "ethX" where X is a number.

    :param interface: the interface name to check
    :return: True if the interface is a cable interface, False otherwise

    Looking at the `man 7 systemd.net-naming-scheme` we can see that
    even the `eth` matching may be an overkill.
    """
    if not isinstance(interface, str) or not interface:
        return False
    return interface.startswith("en") or interface.startswith("eth")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
