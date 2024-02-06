#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2007-2023 Canonical Ltd.
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
        Get default gateway from /sbin/route -n
        Called by get_default_gateway
        and is only used if could not get that from /proc
        """
        logging.debug(
            _("Reading default gateway information from route binary")
        )
        try:
            routebin = subprocess.check_output(
                ["/usr/bin/env", "route", "-n"],
                env={"LANGUAGE": "C"},
                universal_newlines=True,
            )
        except subprocess.CalledProcessError:
            return None
        route_line_re = re.compile(
            r"^0\.0\.0\.0\s+(?P<def_gateway>[\w.]+)(?P<tail>.+)",
            flags=re.MULTILINE,
        )
        route_lines = route_line_re.finditer(routebin)
        for route_line in route_lines:
            def_gateway = route_line.group("def_gateway")
            interface = route_line.group("tail").rsplit(" ", 1)[-1]
            if interface == self.interface and def_gateway:
                return def_gateway
        logging.error(_("Could not find default gateway by running route"))
        return None

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

    @classmethod
    def get_interface_from_ip(cls, ip):
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

    @classmethod
    def get_any_interface(cls):
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

    @classmethod
    def from_ip(cls, ip: str):
        """
        Build an instance of Route given an ip, if no ip is provided the best
        interface that can route to 0.0.0.0/0 is selected (as described by
        metric)
        """
        if ip:
            interface = Route.get_interface_from_ip(ip)
            return Route(interface)
        return Route(Route.get_any_interface())


def is_reachable(ip, interface, verbose=False):
    """
    Ping an ip once to see if it is reachable
    """
    result = ping(ip, interface, 3, 10, verbose)
    return result["transmitted"] >= result["received"] > 0


def get_default_gateway_reachable_on(interface, verbose=False):
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


def get_any_host_reachable_on(interface, verbose=False):
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
        ping(broadcast, interface, 1, 1, broadcast=True, verbose=verbose)
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


def get_host_to_ping(interface: str, target: str = None, verbose=False):
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


def ping(host, interface, count, deadline, broadcast=False, verbose=False):
    command = ["ping", str(host), "-c", str(count), "-w", str(deadline)]
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
    if verbose:
        print(output)
    try:
        received = next(re.finditer(reg, output))
        ping_summary = {
            "transmitted": int(received[1]),
            "received": int(received[2]),
            "pct_loss": int(received[3]),
        }
    except StopIteration:
        ping_summary[
            "cause"
        ] = "Failed to parse the stats from the ping output. Log: {}".format(
            output
        )
    return ping_summary


def parse_args(argv):
    default_count = 2
    default_delay = 4
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "host",
        nargs="?",
        default=None,
        help=_("host to ping"),
    )
    parser.add_argument(
        "-c",
        "--count",
        default=default_count,
        type=int,
        help=_("number of packets to send"),
    )
    parser.add_argument(
        "-d",
        "--deadline",
        default=default_delay,
        type=int,
        help=_("timeout in seconds"),
    )
    parser.add_argument(
        "-t",
        "--threshold",
        default=0,
        type=int,
        help=_("allowed packet loss percentage (default: %(default)s)"),
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help=_("be verbose")
    )
    parser.add_argument(
        "-I", "--interface", help=_("use specified interface to send packets")
    )
    args = parser.parse_args(argv)
    # Ensure count and deadline make sense. Adjust them if not.
    if args.deadline != default_delay and args.count != default_count:
        # Ensure they're both consistent, and exit with a warning if not,
        # rather than modifying what the user explicitly set.
        if args.deadline <= args.count:
            # FIXME: this cannot ever be translated correctly
            raise SystemExit(
                _(
                    "ERROR: not enough time for {0} pings in {1} seconds"
                ).format(args.count, args.deadline)
            )
    elif args.deadline != default_delay:
        # Adjust count according to delay.
        args.count = args.deadline - 1
        if args.count < 1:
            args.count = 1
        if args.verbose:
            # FIXME: this cannot ever be translated correctly
            print(
                _(
                    "Adjusting ping count to {0} to fit in {1}-second deadline"
                ).format(args.count, args.deadline)
            )
    else:
        # Adjust delay according to count
        args.deadline = args.count + 1
        if args.verbose:
            # FIXME: this cannot ever be translated correctly
            print(
                _("Adjusting deadline to {0} seconds to fit {1} pings").format(
                    args.deadline, args.count
                )
            )
    return args


def main(argv) -> int:
    gettext.textdomain("com.canonical.certification.checkbox")
    gettext.bindtextdomain(
        "com.canonical.certification.checkbox",
        os.getenv("CHECKBOX_PROVIDER_LOCALE_DIR", None),
    )

    args = parse_args(argv)

    # If given host is not pingable, override with something pingable.
    host = get_host_to_ping(
        interface=args.interface, verbose=args.verbose, target=args.host
    )
    if args.verbose:
        print(_("Checking connectivity to {0}").format(host))

    if host:
        ping_summary = ping(
            host, args.interface, args.count, args.deadline, args.verbose
        )
    else:
        ping_summary = {
            "received": 0,
            "cause": "Unable to find any host to ping",
        }

    if ping_summary["received"] == 0:
        print(_("No Internet connection"))
        if ping_summary.get("cause"):
            print("Possible cause: {}".format(ping_summary["cause"]))
        return 1
    elif ping_summary["transmitted"] != ping_summary["received"]:
        print(
            _("Connection established, but lost {0}% of packets").format(
                ping_summary["pct_loss"]
            )
        )
        if ping_summary["pct_loss"] > args.threshold:
            print(
                _(
                    "FAIL: {0}% packet loss is higher than {1}% threshold"
                ).format(ping_summary["pct_loss"], args.threshold)
            )
            return 1
        else:
            print(
                _("PASS: {0}% packet loss is within {1}% threshold").format(
                    ping_summary["pct_loss"], args.threshold
                )
            )
            return 0
    else:
        print(_("Connection to test host fully established"))
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
