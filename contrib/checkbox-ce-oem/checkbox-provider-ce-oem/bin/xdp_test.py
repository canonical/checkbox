#!/usr/bin/env python3
# This file is part of Checkbox.
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
"""Ethernet XDP (eXpress Data Path) test helper.

This script drives ``xdp-bench`` to verify the XDP feature of the Linux
kernel in native mode on Ethernet interfaces whose driver supports it.

It supports three modes of operation:

* ``list-ports``: a resource-generator mode that emits one
  ``interface`` record per testable (physical, link up) Ethernet
  interface for the single-port test templates.
* ``pair-ports``: a resource-generator mode that detects the same
  interfaces and emits ring-paired ``source``/``target`` records for
  the redirect test plan.
* ``run``: runs a single XDP action (drop/tx/pass/redirect/redirect-cpu)
  against one interface, self-generating a small amount of L2 traffic
  (raw-socket ARP broadcast) so that packets are guaranteed to arrive,
  then parses the ``xdp-bench`` output to judge pass/fail.

Traffic direction depends on the action:

* Single-port actions (drop/tx/pass/redirect-cpu) send ARP broadcast
  frames from the interface under test itself. This relies on the
  driver's XDP hook seeing these locally-transmitted frames; a driver
  that does not do so would report "no packets received".
* ``redirect`` sends frames from the *target* interface so they enter
  the source interface's RX path and are redirected back to the target.

What can be verified depends on the counters ``xdp-bench`` exposes:
drop checks ``Rx dropped``; redirect checks the received/transmitted
totals; redirect-cpu checks the per-interval cpumap enqueue lines
(extended output). ``xdp-bench`` has no transmit counter for XDP_TX or
XDP_PASS, so those two can only verify that every received frame was
handled without drops or errors.

.. warning::

   Attaching an XDP program may reset the NIC, and ``drop`` discards
   every frame received on the interface for the duration of the run.
   Do not test the interface that carries the Checkbox remote/SSH
   session. A warning is printed when the interface under test holds
   the IPv4 default route.

The code is organised into a small set of cooperating classes so that
individual concerns (interface discovery, traffic generation, tool
invocation, result parsing) can be extended or replaced independently:

* :class:`InterfaceDetector` — discovers physical Ethernet interfaces.
* :class:`TrafficGenerator` — generates L2 ARP broadcast traffic.
* :class:`XdpBenchRunner` — invokes ``xdp-bench`` and captures output;
  raises :class:`XdpBenchError` if it has to be stopped forcibly.
* :class:`ResultChecker` — parses ``xdp-bench`` output and judges
  pass/fail per action.
* :class:`XdpTestRunner` — orchestrates the above for a single action.
"""

import argparse
import fcntl
import re
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

SYS_NET = Path("/sys/class/net")
PROC_NET_ROUTE = Path("/proc/net/route")

# xdp-bench runs for this many seconds before being stopped with SIGINT.
XDP_BENCH_DURATION = 10

# Seconds to wait for xdp-bench to exit after SIGINT, then after SIGTERM.
SIGINT_EXIT_TIMEOUT = 30
SIGTERM_EXIT_TIMEOUT = 5

# Actions that attach to a single interface and share the same options.
BASIC_ACTIONS = ("drop", "tx", "pass")

# redirect: at least this fraction of the received packets must have been
# transmitted on the target interface.
REDIRECT_MIN_RATIO = 0.8

# ioctl request code for SIOCGIFHWADDR (get interface MAC address).
SIOCGIFHWADDR = 0x8927

# Ethernet frame type for ARP (0x0806).
ETH_P_ARP = 0x0806


def _to_int(text):
    """Convert a possibly thousands-separated number ('1,234') to int.

    xdp-bench calls setlocale(LC_NUMERIC, "en_US.UTF-8"), so its
    counters may contain thousands separators.
    """
    return int(text.replace(",", ""))


class InterfaceDetector:
    """Discover physical Ethernet interfaces suitable for XDP testing.

    A "testable" interface is a physical (non-virtual) Ethernet device
    that currently reports carrier (link) up. Wireless and wwan
    interfaces are excluded explicitly.
    """

    def __init__(
        self, sys_net: Path = SYS_NET, proc_route: Path = PROC_NET_ROUTE
    ):
        self._sys_net = sys_net
        self._proc_route = proc_route

    @staticmethod
    def _is_ethernet_type(base: Path) -> bool:
        """Return False only if sysfs says the link type is not Ethernet.

        ``type`` is the ARPHRD value; 1 is ARPHRD_ETHER.
        """
        try:
            return (base / "type").read_text().strip() == "1"
        except OSError:
            return True

    @staticmethod
    def _is_wwan(base: Path) -> bool:
        """Return True if the netdev is a WWAN modem interface."""
        try:
            lines = (base / "uevent").read_text().splitlines()
        except OSError:
            return False
        return "DEVTYPE=wwan" in lines

    def is_physical_ethernet(self, iface: str) -> bool:
        """Return True if ``iface`` is a physical Ethernet interface.

        Physical interfaces have a ``device`` symlink under
        ``/sys/class/net/<iface>/``. Virtual interfaces (lo, docker0,
        veth*, br-*, ...) do not. Wireless interfaces (``wireless`` /
        ``phy80211``), WWAN modems (``DEVTYPE=wwan``) and anything that is
        not ARPHRD_ETHER are excluded explicitly.
        """
        if iface == "lo":
            return False
        base = self._sys_net / iface
        if not (base / "device").is_symlink():
            return False
        if (base / "wireless").exists() or (base / "phy80211").exists():
            return False
        if self._is_wwan(base):
            return False
        return self._is_ethernet_type(base)

    def has_link(self, iface: str) -> bool:
        """Return True if ``iface`` reports carrier (link) up."""
        carrier = self._sys_net / iface / "carrier"
        try:
            return carrier.read_text().strip() == "1"
        except OSError:
            return False

    def default_route_interfaces(self):
        """Return the set of interfaces holding an IPv4 default route.

        Parsed from ``/proc/net/route`` (columns: Iface, Destination,
        Gateway, ...); a destination of 00000000 is a default route.
        """
        try:
            lines = self._proc_route.read_text().splitlines()
        except OSError:
            return set()
        ifaces = set()
        for line in lines[1:]:
            fields = line.split()
            if len(fields) >= 2 and fields[1] == "00000000":
                ifaces.add(fields[0])
        return ifaces

    @staticmethod
    def _natural_key(name):
        """Return a sort key that orders digits numerically (eth2 < eth10)."""
        return [
            int(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", name)
        ]

    def list_test_interfaces(self):
        """Return naturally-sorted list of physical Ethernet interfaces
        with link."""
        ifaces = [
            iface.name
            for iface in self._sys_net.iterdir()
            if self.is_physical_ethernet(iface.name)
            and self.has_link(iface.name)
        ]
        return sorted(ifaces, key=self._natural_key)


class TrafficGenerator:
    """Generate L2 ARP broadcast traffic on an interface.

    Uses a raw AF_PACKET socket (no external arping dependency) and
    works at L2, so the interface does not need an IP address or a
    gateway. Traffic is sent from a background thread until ``stop()``
    is called.
    """

    def __init__(self, iface: str, interval: float = 0.2):
        self._iface = iface
        self._interval = interval
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._thread = None
        # Set when the socket cannot be set up (fatal for the test).
        self.setup_error = None
        # Send statistics. Individual send failures are tolerated because
        # the driver may briefly reset the NIC when the XDP program is
        # attached; see failure() for the final verdict.
        self.sent = 0
        self.send_errors = 0
        self.last_send_error = None

    @staticmethod
    def _get_mac(iface: str) -> bytes:
        """Return the 6-byte MAC address of ``iface`` via SIOCGIFHWADDR."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            info = fcntl.ioctl(
                sock.fileno(),
                SIOCGIFHWADDR,
                struct.pack("256s", iface[:15].encode()),
            )
            return info[18:24]
        finally:
            sock.close()

    @staticmethod
    def _build_arp_frame(src_mac: bytes) -> bytes:
        """Build an unsolicited ARP request frame (broadcast, 0.0.0.0)."""
        # Ethernet header: broadcast dst + src MAC + ARP ethertype.
        eth = b"\xff" * 6 + src_mac + struct.pack("!H", ETH_P_ARP)
        # ARP header: htype=1 (Ethernet), ptype=0x0800 (IPv4), hlen=6,
        # plen=4, op=1 (request).
        arp = struct.pack("!HHBBH", 1, 0x0800, 6, 4, 1)
        # Sender MAC + sender IP (0.0.0.0), target MAC + target IP (0.0.0.0).
        arp += src_mac + struct.pack("!I", 0)
        arp += b"\x00" * 6 + struct.pack("!I", 0)
        return eth + arp

    def _open_socket(self):
        """Return a bound AF_PACKET socket and the frame to send on it."""
        sock = socket.socket(
            socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ARP)
        )
        try:
            sock.bind((self._iface, 0))
            frame = self._build_arp_frame(self._get_mac(self._iface))
        except OSError:
            sock.close()
            raise
        return sock, frame

    def _send_arp_loop(self):
        """Continuously send ARP broadcast frames until stopped.

        Setup failures are recorded in ``setup_error`` and end the thread.
        Send failures are only counted, so that traffic resumes once the
        interface comes back after the XDP program was attached.
        """
        try:
            sock, frame = self._open_socket()
        except OSError as exc:
            self.setup_error = "cannot send traffic on {}: {}".format(
                self._iface, exc
            )
            return
        finally:
            self._ready_event.set()
        try:
            while not self._stop_event.is_set():
                try:
                    sock.send(frame)
                    self.sent += 1
                except OSError as exc:
                    self.send_errors += 1
                    self.last_send_error = exc
                self._stop_event.wait(self._interval)
        finally:
            sock.close()

    def start(self, timeout: float = 2.0):
        """Start the background traffic thread.

        Waits until the socket is set up (or setup failed), so that
        ``setup_error`` can be checked right after this call.
        """
        self._thread = threading.Thread(
            target=self._send_arp_loop, daemon=True
        )
        self._thread.start()
        self._ready_event.wait(timeout=timeout)

    def stop(self, timeout: float = 2.0):
        """Stop the background traffic thread and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def failure(self):
        """Return a message if no traffic could be generated, else None.

        Meant to be called after ``stop()``.
        """
        if self.setup_error:
            return self.setup_error
        if self.sent == 0:
            reason = ""
            if self.last_send_error is not None:
                reason = " (last error: {})".format(self.last_send_error)
            return "no traffic could be generated on {}{}".format(
                self._iface, reason
            )
        return None


class XdpBenchError(Exception):
    """Raised when xdp-bench had to be stopped forcibly."""

    def __init__(self, message, output=""):
        super().__init__(message)
        self.output = output


class XdpBenchRunner:
    """Invoke ``xdp-bench`` for a single XDP action and capture output."""

    def __init__(
        self,
        duration: int = XDP_BENCH_DURATION,
        exit_timeout: float = SIGINT_EXIT_TIMEOUT,
        terminate_timeout: float = SIGTERM_EXIT_TIMEOUT,
    ):
        self._duration = duration
        self._exit_timeout = exit_timeout
        self._terminate_timeout = terminate_timeout

    @staticmethod
    def build_command(action, iface, target=None):
        """Return the xdp-bench command line for ``action``."""
        cmd = ["xdp-bench", action, "-m", "native"]
        if action in BASIC_ACTIONS:
            # ARP frames are not IP, so modes that parse the IP header
            # (parse-ip) may reject them. no-touch applies the action to
            # every frame unmodified.
            cmd += ["-p", "no-touch", iface]
        elif action == "redirect":
            if not target:
                raise ValueError("redirect requires a target interface")
            cmd += ["-s", iface, target]
        elif action == "redirect-cpu":
            # no-touch always picks the first CPU, whereas the default
            # l4-hash policy is meant for IP traffic. -e (extended output)
            # is required to get the per-interval "enqueue to cpu N" lines
            # that ResultChecker uses to confirm the redirect happened.
            cmd += ["-c", "0", "-p", "no-touch", "-e", "-s", iface]
        else:
            raise ValueError("unknown action '{}'".format(action))
        return cmd

    def run(self, action, iface, target=None):
        """Run xdp-bench for ``action`` and return (returncode, output).

        xdp-bench runs until it receives SIGINT, at which point it prints
        its statistics and exits cleanly (unloading the XDP program). We
        start it, let it run for ``duration`` seconds, then send SIGINT
        and collect the output.

        If it does not exit in time it is stopped with SIGTERM (which
        xdp-bench also handles by detaching), then SIGKILL as a last
        resort. The XDP program is then detached from ``iface`` by hand
        and :class:`XdpBenchError` is raised, because a forced stop means
        the statistics are unreliable and the interface could otherwise
        be left with a stale XDP program.
        """
        cmd = self.build_command(action, iface, target)
        print("Command: {}".format(" ".join(cmd)))
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        try:
            time.sleep(self._duration)
            proc.send_signal(signal.SIGINT)
            output, _ = proc.communicate(timeout=self._exit_timeout)
        except subprocess.TimeoutExpired:
            output = self._force_stop(proc)
            self._detach_xdp(iface)
            raise XdpBenchError(
                "xdp-bench did not exit within {}s after SIGINT and was "
                "stopped forcibly".format(self._exit_timeout),
                output,
            )
        return proc.returncode, output

    def _force_stop(self, proc):
        """Stop ``proc`` with SIGTERM, then SIGKILL; return its output."""
        proc.terminate()
        try:
            output, _ = proc.communicate(timeout=self._terminate_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
        return output

    @staticmethod
    def _detach_xdp(iface):
        """Detach any XDP program left on ``iface`` (best effort)."""
        cmd = ["ip", "link", "set", "dev", iface, "xdp", "off"]
        print("Cleanup: {}".format(" ".join(cmd)))
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        except OSError as exc:
            print("Warning: could not run ip: {}".format(exc))
            return
        if result.returncode != 0:
            print(
                "Warning: failed to detach XDP from {}: {}".format(
                    iface, result.stdout.strip()
                )
            )


class ResultChecker:
    """Parse ``xdp-bench`` output and judge pass/fail per action."""

    NO_PACKETS = "no packets received (is the interface up with link?)"

    @staticmethod
    def parse_errors(output):
        """Return True if xdp-bench reported any error.

        Looks at the per-interval ``err/s`` / ``err,drop/s`` columns and
        at the ``Errors recorded`` total of the final summary.
        """
        # Matches "0 err/s" and "0 err,drop/s" columns.
        for m in re.finditer(r"(\d[\d,]*)\s+err(?:,drop)?/s", output):
            if _to_int(m.group(1)) != 0:
                return True
        return bool(ResultChecker.parse_int_field(output, "Errors recorded"))

    @staticmethod
    def parse_int_field(output, field):
        """Parse an integer field like 'Packets received    : 1,013'."""
        m = re.search(r"{}\s*:\s*(\d[\d,]*)".format(re.escape(field)), output)
        return _to_int(m.group(1)) if m else None

    @staticmethod
    def parse_cpu_enqueue(output):
        """Sum the ``enqueue to cpu N`` pkt/s values of all intervals.

        These lines are only printed in extended output mode.
        """
        total = 0
        for m in re.finditer(
            r"enqueue to cpu\s+\d+\s+(\d[\d,]*)\s+pkt/s", output
        ):
            total += _to_int(m.group(1))
        return total

    def _require_received(self, output):
        """Return (received, None) or (None, error message)."""
        received = self.parse_int_field(output, "Packets received")
        if received is None:
            return None, "could not parse packet counters"
        if received == 0:
            return None, self.NO_PACKETS
        return received, None

    def _check_basic(self, output, verdict):
        """Shared check for tx/pass: received, none dropped."""
        received, error = self._require_received(output)
        if error:
            return False, error
        dropped = self.parse_int_field(output, "Rx dropped") or 0
        if dropped:
            return (
                False,
                "{} of {} packets were dropped instead of being handled "
                "by {}".format(dropped, received, verdict),
            )
        return True, "{} packets handled by {} without drops".format(
            received, verdict
        )

    def check_drop(self, output):
        """drop: every received packet must be counted as Rx dropped."""
        received, error = self._require_received(output)
        if error:
            return False, error
        dropped = self.parse_int_field(output, "Rx dropped") or 0
        if dropped != received:
            return (
                False,
                "Rx dropped ({}) != Packets received ({})".format(
                    dropped, received
                ),
            )
        return True, "all {} packets dropped at XDP".format(received)

    def check_tx(self, output):
        """tx: packets must be received and none dropped.

        xdp-bench has no transmit counter for XDP_TX, so this cannot prove
        that the frames left the interface; it verifies that every
        received packet was handled without drops (errors are rejected
        separately by :meth:`parse_errors`).
        """
        return self._check_basic(output, "XDP_TX")

    def check_pass(self, output):
        """pass: packets must be received and none dropped.

        xdp-bench cannot tell whether the kernel stack saw the packets;
        like :meth:`check_tx` this verifies that every received packet
        was handled by XDP_PASS without drops.
        """
        return self._check_basic(output, "XDP_PASS")

    def check_redirect(self, output):
        """redirect: packets received and transmitted on the target.

        At least ``REDIRECT_MIN_RATIO`` of the received packets must have
        been transmitted. Errors are rejected separately by
        :meth:`parse_errors`.
        """
        received, error = self._require_received(output)
        if error:
            return False, error
        transmitted = self.parse_int_field(output, "Packets transmitted") or 0
        if transmitted == 0:
            return False, "no packets transmitted (redirect target down?)"
        if transmitted < received * REDIRECT_MIN_RATIO:
            return (
                False,
                "only {} of {} received packets were transmitted "
                "(minimum {:.0%})".format(
                    transmitted, received, REDIRECT_MIN_RATIO
                ),
            )
        return True, "{} packets redirected ({} transmitted)".format(
            received, transmitted
        )

    def check_redirect_cpu(self, output):
        """redirect-cpu: packets received and enqueued to the target CPU.

        The cpumap enqueue statistics are only printed in extended output
        mode, which :class:`XdpBenchRunner` enables for this action.
        """
        received, error = self._require_received(output)
        if error:
            return False, error
        if self.parse_cpu_enqueue(output) == 0:
            return (
                False,
                "{} packets received but none were enqueued to the "
                "target CPU".format(received),
            )
        return True, "{} packets received, redirect to CPU observed".format(
            received
        )

    def check(self, action, output):
        """Dispatch to the per-action checker and return (ok, message)."""
        checkers = {
            "drop": self.check_drop,
            "tx": self.check_tx,
            "pass": self.check_pass,
            "redirect": self.check_redirect,
            "redirect-cpu": self.check_redirect_cpu,
        }
        return checkers[action](output)


class XdpTestRunner:
    """Orchestrate a single XDP action end-to-end and judge pass/fail."""

    def __init__(
        self,
        detector: InterfaceDetector = None,
        bench: XdpBenchRunner = None,
        checker: ResultChecker = None,
    ):
        self._detector = detector or InterfaceDetector()
        self._bench = bench or XdpBenchRunner()
        self._checker = checker or ResultChecker()

    def list_interfaces(self):
        """Return the testable (physical, link up) interface names."""
        return self._detector.list_test_interfaces()

    def emit_ports(self, ifaces):
        """Print one ``interface`` resource record per interface."""
        for iface in ifaces:
            print("interface: {}".format(iface))
            print()

    def _warn_if_default_route(self, iface):
        """Warn if ``iface`` may be the management interface."""
        if iface in self._detector.default_route_interfaces():
            print(
                "Warning: {} holds the IPv4 default route; if it is the "
                "management interface the connection may drop while the "
                "XDP program is attached".format(iface)
            )

    def emit_pairing(self, ifaces):
        """Print ring-paired source/target resource records.

        Each interface redirects to the next one in sorted order; the
        last redirects back to the first. With a single interface no
        records are emitted (the redirect template expands to zero jobs).
        """
        n = len(ifaces)
        if n < 2:
            return
        for i, src in enumerate(ifaces):
            tgt = ifaces[(i + 1) % n]
            print("source: {}".format(src))
            print("target: {}".format(tgt))
            print()

    def run_action(self, action, iface, target=None):
        """Run a single XDP action and judge pass/fail."""
        print("Running XDP {} on {} (native mode)".format(action, iface))
        if action == "redirect-cpu":
            print("Redirecting from {} to CPU 0".format(iface))
        self._warn_if_default_route(iface)

        # Single-port actions generate traffic from the interface under
        # test; redirect generates traffic from the target so frames enter
        # the source interface's RX path.
        traffic_iface = target if action == "redirect" else iface
        generator = TrafficGenerator(traffic_iface)
        generator.start()
        try:
            if generator.setup_error:
                print("Fail: {}".format(generator.setup_error))
                return 1
            # Give the traffic generator a moment to start before xdp-bench.
            time.sleep(1)
            try:
                rc, output = self._bench.run(action, iface, target)
            except XdpBenchError as exc:
                print(exc.output)
                print("Fail: {}".format(exc))
                return 1
        finally:
            generator.stop()

        print(output)

        if rc != 0:
            # xdp-bench returns non-zero on "Operation not supported" etc.
            if "Operation not supported" in output:
                print(
                    "Fail: driver does not support XDP native mode for "
                    "this interface"
                )
            else:
                print("Fail: xdp-bench exited with status {}".format(rc))
            return 1

        if generator.send_errors:
            print(
                "Note: {} frame(s) could not be sent on {} (last error: "
                "{})".format(
                    generator.send_errors,
                    traffic_iface,
                    generator.last_send_error,
                )
            )
        traffic_failure = generator.failure()
        if traffic_failure:
            print("Fail: {}".format(traffic_failure))
            return 1

        if self._checker.parse_errors(output):
            print("Fail: non-zero err/s observed")
            return 1

        ok, msg = self._checker.check(action, output)
        if not ok:
            print("Fail: {}".format(msg))
            return 1

        print("Success: {}".format(msg))
        return 0


def main():
    parser = argparse.ArgumentParser(description="RZ XDP test helper")
    parser.add_argument(
        "--action",
        required=True,
        choices=(
            "list-ports",
            "pair-ports",
            "drop",
            "tx",
            "pass",
            "redirect",
            "redirect-cpu",
        ),
        help=(
            "XDP action to run, or 'list-ports' / 'pair-ports' to emit "
            "resource records"
        ),
    )
    parser.add_argument(
        "--interface", help="interface to test (required for run actions)"
    )
    parser.add_argument(
        "--target", help="redirect target interface (redirect action only)"
    )
    args = parser.parse_args()

    runner = XdpTestRunner()

    if args.action == "list-ports":
        runner.emit_ports(runner.list_interfaces())
        return 0

    if args.action == "pair-ports":
        runner.emit_pairing(runner.list_interfaces())
        return 0

    if not args.interface:
        raise SystemExit(
            "Error: --interface is required for '{}'".format(args.action)
        )

    if args.action == "redirect" and not args.target:
        raise SystemExit("Error: --target is required for 'redirect'")

    return runner.run_action(args.action, args.interface, args.target)


if __name__ == "__main__":
    sys.exit(main())
