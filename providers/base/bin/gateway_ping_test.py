#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2007-2014 Canonical Ltd.
# Written by:
#   Brendan Donegan <brendan.donegan@canonical.com>
#   Daniel Manrique <daniel.manrique@canonical.com>
#   David Murphy <david.murphy@canonical.com>
#   Javier Collado <javier.collado@canonical.com>
#   Jeff Lane <jeffrey.lane@canonical.com>
#   Marc Tardif <marc.tardif@canonical.com>
#   Mathieu Trudel-Lapierre <mathieu.trudel-lapierre@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
import errno
import gettext
import logging
import os
import re
import socket
import struct
import subprocess
import sys
import time


class Route:
    """
    Gets routing information from the system.
    """

    def _num_to_dotted_quad(self, number):
        """
        Convert long int to dotted quad string
        """
        return socket.inet_ntoa(struct.pack("<L", number))

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
        else:
            h = re.compile(r"\n(?P<interface>\w+)\s+00000000\s+"
                           r"(?P<def_gateway>[\w]+)\s+")
            w = h.search(route)
            if w:
                if w.group("def_gateway"):
                    return self._num_to_dotted_quad(
                        int(w.group("def_gateway"), 16))
                else:
                    logging.error(
                        _("Could not find def gateway info in /proc"))
                    return None
            else:
                logging.error(_("Could not find def gateway info in /proc"))
                return None

    def _get_default_gateway_from_bin_route(self):
        """
        Get default gateway from /sbin/route -n
        Called by get_default_gateway
        and is only used if could not get that from /proc
        """
        logging.debug(
            _("Reading default gateway information from route binary"))
        routebin = subprocess.getstatusoutput(
            "export LANGUAGE=C; " "/usr/bin/env route -n")
        if routebin[0] == 0:
            h = re.compile(r"\n0.0.0.0\s+(?P<def_gateway>[\w.]+)\s+")
            w = h.search(routebin[1])
            if w:
                def_gateway = w.group("def_gateway")
                if def_gateway:
                    return def_gateway
        logging.error(_("Could not find default gateway by running route"))
        return None

    def get_hostname(self):
        return socket.gethostname()

    def get_default_gateway(self):
        t1 = self._get_default_gateway_from_proc()
        if not t1:
            t1 = self._get_default_gateway_from_bin_route()
        return t1


def get_host_to_ping(interface=None, verbose=False, default=None):
    # Get list of all IPs from all my interfaces,
    interface_list = subprocess.check_output(["ip", "-o", 'addr', 'show'])
    reg = re.compile(r'\d: (?P<iface>\w+) +inet (?P<address>[\d\.]+)/'
                     r'(?P<netmask>[\d]+) brd (?P<broadcast>[\d\.]+)')
    # Will magically exclude lo because it lacks brd field
    interfaces = reg.findall(interface_list.decode())
    # ping -b the network on each one (one ping only)
    # exclude the ones not specified in iface
    for iface in interfaces:
        if not interface or iface[0] == interface:
            # Use check_output even if I'll discard the output
            # looks cleaner than using .call and redirecting stdout to null
            try:
                subprocess.check_output(["ping", "-q", "-c", "1", "-b",
                                         iface[3]], stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                pass
    # If default host given, ping it as well,
    # to try to get it into the arp table.
    # Needed in case it's not responding to broadcasts.
    if default:
        try:
            subprocess.check_output(["ping", "-q", "-c", "1", default],
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            pass
    # Try to get the gateway address for the interface from networkctl
    cmd = 'networkctl status --no-pager --no-legend {}'.format(interface)
    try:
        output = subprocess.check_output(cmd, shell=True)
        for line in output.decode(sys.stdout.encoding).splitlines():
            vals = line.strip().split(' ')
            if len(vals) >= 2:
                if vals[0] == 'Gateway:':
                    subprocess.check_output(["ping", "-q", "-c", "1", vals[1]],
                                            stderr=subprocess.STDOUT)
                    break
    except subprocess.CalledProcessError:
        pass
    ARP_POPULATE_TRIES = 10
    num_tries = 0
    while num_tries < ARP_POPULATE_TRIES:
        # Get output from arp -a -n to get known IPs
        known_ips = subprocess.check_output(["arp", "-a", "-n"])
        reg = re.compile(r'\? \((?P<ip>[\d.]+)\) at (?P<mac>[a-f0-9\:]+) '
                         r'\[ether\] on (?P<iface>[\w\d]+)')
        # Filter (if needed) IPs not on the specified interface
        pingable_ips = [pingable[0] for pingable in reg.findall(
                        known_ips.decode()) if not interface or
                        pingable[2] == interface]
        # If the default given ip is among the remaining ones,
        # ping that.
        if default and default in pingable_ips:
            if verbose:
                print(_(
                    "Desired ip address {0} is reachable, using it"
                ).format(default))
            return default
        # If not, choose another IP.
        address_to_ping = pingable_ips[0] if len(pingable_ips) else None
        if verbose:
            print(_(
                "Desired ip address {0} is not reachable from {1},"
                " using {2} instead"
            ).format(default, interface, address_to_ping))
        if address_to_ping:
            return address_to_ping
        time.sleep(2)
        num_tries += 1
    # Wait time expired
    return None


def ping(host, interface, count, deadline, verbose=False):
    command = ["ping", str(host),  "-c", str(count), "-w", str(deadline)]
    if interface:
        command.append("-I{}".format(interface))
    reg = re.compile(
        r"(\d+) packets transmitted, (\d+) received,"
        r".*([0-9]*\.?[0-9]*.)% packet loss")
    ping_summary = {'transmitted': 0, 'received': 0, 'pct_loss': 0}
    try:
        output = subprocess.check_output(
            command, universal_newlines=True, stderr=subprocess.PIPE)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            # No ping command present;
            # default exception message is informative enough.
            print(exc)
        else:
            raise
    except subprocess.CalledProcessError as excp:
        # Ping returned fail exit code
        print(_("ERROR: ping result: {0}").format(excp))
        if excp.stderr:
            print(excp.stderr)
            if 'SO_BINDTODEVICE' in excp.stderr:
                ping_summary['cause'] = (
                    "Could not bind to the {} interface.".format(interface))
    else:
        if verbose:
            print(output)
        received = re.findall(reg, output)
        if received:
            ping_summary = received[0]
            ping_summary = {
                'transmitted': int(ping_summary[0]),
                'received': int(ping_summary[1]),
                'pct_loss': int(ping_summary[2])}
    return ping_summary


def parse_args(argv):
    default_count = 2
    default_delay = 4
    route = Route()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "host",
        nargs="?",
        default=route.get_default_gateway(),
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
        interface=args.interface, verbose=args.verbose, default=args.host
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
