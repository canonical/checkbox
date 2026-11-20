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

import io
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import xdp_test

# Output of the per-interval enqueue line printed by xdp-bench redirect-cpu
# in extended mode.
ENQUEUE_LINE = (
    "  enqueue to cpu 0          13 pkt/s           0 drop/s"
    "        1.00 bulk-avg\n"
)


class FakeProc:
    """Minimal stand-in for subprocess.Popen.

    ``results`` is a list consumed by successive communicate() calls; an
    exception instance in the list is raised instead of returned.
    """

    def __init__(self, results=None, returncode=0):
        self.returncode = returncode
        self._results = list(
            results if results is not None else [("out\n", None)]
        )
        self.signals = []
        self.terminated = False
        self.killed = False

    def send_signal(self, sig):
        self.signals.append(sig)

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def communicate(self, timeout=None):
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _timeout():
    return subprocess.TimeoutExpired(cmd="xdp-bench", timeout=1)


class ResultCheckerTestCase(unittest.TestCase):
    def setUp(self):
        self.checker = xdp_test.ResultChecker()

    def test_parse_int_field(self):
        out = "Packets received    : 13\nRx dropped : 13\n"
        self.assertEqual(
            self.checker.parse_int_field(out, "Packets received"), 13
        )
        self.assertEqual(self.checker.parse_int_field(out, "Rx dropped"), 13)
        self.assertIsNone(
            self.checker.parse_int_field(out, "Packets transmitted")
        )

    def test_parse_errors_no_errors(self):
        out = "Summary 3 rx/s 0 err/s\nend3->end2 2 rx/s 0 err,drop/s\n"
        self.assertFalse(self.checker.parse_errors(out))

    def test_parse_errors_with_errors(self):
        out = "Summary 3 rx/s 1 err/s\n"
        self.assertTrue(self.checker.parse_errors(out))

    def test_parse_errors_thousands_separator(self):
        out = "Summary 3 rx/s 1,000 err,drop/s\n"
        self.assertTrue(self.checker.parse_errors(out))

    def test_parse_errors_summary_total(self):
        out = "Summary 3 rx/s 0 err/s\n  Errors recorded     : 4\n"
        self.assertTrue(self.checker.parse_errors(out))

    def test_parse_errors_summary_total_zero(self):
        out = "Summary 3 rx/s 0 err/s\n  Errors recorded     : 0\n"
        self.assertFalse(self.checker.parse_errors(out))

    def test_parse_errors_ignores_error_column_label(self):
        # Extended mode prints "error/s" columns which are not matched.
        out = "  receive total  13 pkt/s  0 drop/s  7 error/s\n"
        self.assertFalse(self.checker.parse_errors(out))

    def test_parse_int_field_thousands_separator(self):
        out = "Packets received    : 1,234,567\n"
        self.assertEqual(
            self.checker.parse_int_field(out, "Packets received"), 1234567
        )

    def test_parse_cpu_enqueue(self):
        out = ENQUEUE_LINE + ENQUEUE_LINE.replace("13 pkt/s", "1,000 pkt/s")
        self.assertEqual(self.checker.parse_cpu_enqueue(out), 1013)

    def test_parse_cpu_enqueue_absent(self):
        self.assertEqual(
            self.checker.parse_cpu_enqueue("Packets received : 5\n"), 0
        )

    def test_parse_cpu_enqueue_ignores_per_cpu_lines(self):
        out = "    cpu:0->0              13 pkt/s     0 drop/s\n"
        self.assertEqual(self.checker.parse_cpu_enqueue(out), 0)

    def test_check_drop_success(self):
        out = "Packets received    : 13\nRx dropped : 13\n"
        ok, msg = self.checker.check_drop(out)
        self.assertTrue(ok)
        self.assertIn("13", msg)

    def test_check_drop_mismatch(self):
        out = "Packets received    : 13\nRx dropped : 5\n"
        ok, msg = self.checker.check_drop(out)
        self.assertFalse(ok)
        self.assertIn("Rx dropped", msg)

    def test_check_drop_no_packets(self):
        out = "Packets received    : 0\nRx dropped : 0\n"
        ok, _ = self.checker.check_drop(out)
        self.assertFalse(ok)

    def test_check_drop_unparsable(self):
        ok, msg = self.checker.check_drop("garbage\n")
        self.assertFalse(ok)
        self.assertIn("could not parse", msg)

    def test_check_drop_missing_dropped_counter(self):
        # xdp-bench omits "Rx dropped" when it is zero.
        ok, msg = self.checker.check_drop("Packets received    : 13\n")
        self.assertFalse(ok)
        self.assertIn("Rx dropped (0)", msg)

    def test_check_drop_thousands_separator(self):
        out = "Packets received    : 1,234\nRx dropped : 1,234\n"
        ok, _ = self.checker.check_drop(out)
        self.assertTrue(ok)

    def test_check_tx_success(self):
        out = "Packets received    : 7\n"
        ok, msg = self.checker.check_tx(out)
        self.assertTrue(ok)
        self.assertIn("XDP_TX", msg)

    def test_check_tx_dropped(self):
        out = "Packets received    : 7\nRx dropped          : 2\n"
        ok, msg = self.checker.check_tx(out)
        self.assertFalse(ok)
        self.assertIn("2 of 7", msg)

    def test_check_tx_no_packets(self):
        ok, msg = self.checker.check_tx("Packets received    : 0\n")
        self.assertFalse(ok)
        self.assertEqual(msg, self.checker.NO_PACKETS)

    def test_check_tx_unparsable(self):
        ok, msg = self.checker.check_tx("garbage\n")
        self.assertFalse(ok)
        self.assertIn("could not parse", msg)

    def test_check_pass_success(self):
        out = "Packets received    : 7\n"
        ok, msg = self.checker.check_pass(out)
        self.assertTrue(ok)
        self.assertIn("XDP_PASS", msg)

    def test_check_pass_dropped(self):
        out = "Packets received    : 7\nRx dropped          : 7\n"
        ok, msg = self.checker.check_pass(out)
        self.assertFalse(ok)
        self.assertIn("XDP_PASS", msg)

    def test_check_pass_no_packets(self):
        ok, _ = self.checker.check_pass("Packets received    : 0\n")
        self.assertFalse(ok)

    def test_check_redirect_success(self):
        out = "Packets received    : 11\nPackets transmitted : 11\n"
        ok, _ = self.checker.check_redirect(out)
        self.assertTrue(ok)

    def test_check_redirect_no_transmit(self):
        out = "Packets received    : 11\nPackets transmitted : 0\n"
        ok, _ = self.checker.check_redirect(out)
        self.assertFalse(ok)

    def test_check_redirect_transmit_counter_missing(self):
        ok, msg = self.checker.check_redirect("Packets received    : 11\n")
        self.assertFalse(ok)
        self.assertIn("no packets transmitted", msg)

    def test_check_redirect_no_packets(self):
        out = "Packets received    : 0\nPackets transmitted : 0\n"
        ok, msg = self.checker.check_redirect(out)
        self.assertFalse(ok)
        self.assertEqual(msg, self.checker.NO_PACKETS)

    def test_check_redirect_ratio_at_threshold(self):
        out = "Packets received    : 100\nPackets transmitted : 80\n"
        ok, _ = self.checker.check_redirect(out)
        self.assertTrue(ok)

    def test_check_redirect_ratio_below_threshold(self):
        out = "Packets received    : 100\nPackets transmitted : 79\n"
        ok, msg = self.checker.check_redirect(out)
        self.assertFalse(ok)
        self.assertIn("79 of 100", msg)

    def test_check_redirect_unparsable(self):
        ok, msg = self.checker.check_redirect("garbage\n")
        self.assertFalse(ok)
        self.assertIn("could not parse", msg)

    def test_check_redirect_cpu_success(self):
        out = "Packets received    : 52\n" + ENQUEUE_LINE
        ok, _ = self.checker.check_redirect_cpu(out)
        self.assertTrue(ok)

    def test_check_redirect_cpu_not_enqueued(self):
        # Packets reached the XDP hook but were never sent to a CPU.
        out = "Packets received    : 52\n"
        ok, msg = self.checker.check_redirect_cpu(out)
        self.assertFalse(ok)
        self.assertIn("none were enqueued", msg)

    def test_check_redirect_cpu_unparsable(self):
        ok, msg = self.checker.check_redirect_cpu("garbage\n")
        self.assertFalse(ok)
        self.assertIn("could not parse", msg)

    def test_check_redirect_cpu_no_packets(self):
        out = "Packets received    : 0\n"
        ok, _ = self.checker.check_redirect_cpu(out)
        self.assertFalse(ok)

    def test_check_dispatch(self):
        out = "Packets received    : 7\n"
        ok, _ = self.checker.check("tx", out)
        self.assertTrue(ok)

    def test_check_dispatch_redirect_cpu(self):
        out = "Packets received    : 7\n" + ENQUEUE_LINE
        ok, _ = self.checker.check("redirect-cpu", out)
        self.assertTrue(ok)


class TrafficGeneratorTestCase(unittest.TestCase):
    def test_build_arp_frame_structure(self):
        src_mac = b"\x0e\x26\x05\x38\x85\x51"
        frame = xdp_test.TrafficGenerator._build_arp_frame(src_mac)
        # Ethernet header: 6 dst + 6 src + 2 ethertype = 14 bytes.
        self.assertEqual(len(frame), 14 + 28)
        # Broadcast destination MAC.
        self.assertEqual(frame[0:6], b"\xff" * 6)
        # Source MAC.
        self.assertEqual(frame[6:12], src_mac)
        # ARP ethertype 0x0806 (big-endian).
        self.assertEqual(frame[12:14], b"\x08\x06")
        # ARP htype=1 (Ethernet), ptype=0x0800 (IPv4).
        self.assertEqual(frame[14:16], b"\x00\x01")
        self.assertEqual(frame[16:18], b"\x08\x00")
        # hlen=6, plen=4.
        self.assertEqual(frame[18], 6)
        self.assertEqual(frame[19], 4)
        # op=1 (request).
        self.assertEqual(frame[20:22], b"\x00\x01")
        # Sender MAC.
        self.assertEqual(frame[22:28], src_mac)
        # Sender IP 0.0.0.0.
        self.assertEqual(frame[28:32], b"\x00\x00\x00\x00")
        # Target MAC (zero) + target IP 0.0.0.0.
        self.assertEqual(frame[32:38], b"\x00" * 6)
        self.assertEqual(frame[38:42], b"\x00\x00\x00\x00")

    def test_get_mac(self):
        mac = b"\x0e\x26\x05\x38\x85\x51"
        ifreq = b"\x00" * 18 + mac + b"\x00" * (256 - 24)
        with patch("xdp_test.socket") as mock_socket, patch(
            "xdp_test.fcntl.ioctl", return_value=ifreq
        ):
            self.assertEqual(xdp_test.TrafficGenerator._get_mac("eth0"), mac)
        mock_socket.socket.return_value.close.assert_called_once_with()


class TrafficGeneratorLoopTestCase(unittest.TestCase):
    """The background thread: setup errors, send errors, bookkeeping."""

    FRAME_MAC = b"\x00\x11\x22\x33\x44\x55"

    def _make_socket(self, send=None, sent_event=None):
        sock = MagicMock()

        def _send(frame):
            try:
                if send is not None:
                    send(frame)
            finally:
                if sent_event is not None:
                    sent_event.set()

        sock.send.side_effect = _send
        return sock

    def _run(self, sock, wait_for):
        """Run a generator against ``sock`` until ``wait_for`` is set."""
        gen = xdp_test.TrafficGenerator("eth0", interval=0.001)
        with patch("xdp_test.socket") as mock_socket, patch.object(
            xdp_test.TrafficGenerator, "_get_mac", return_value=self.FRAME_MAC
        ):
            mock_socket.socket.return_value = sock
            gen.start()
            self.assertTrue(wait_for.wait(timeout=5))
            gen.stop()
        return gen

    def test_setup_error_socket(self):
        gen = xdp_test.TrafficGenerator("eth0")
        with patch("xdp_test.socket") as mock_socket:
            mock_socket.socket.side_effect = PermissionError(
                1, "not permitted"
            )
            gen.start()
            gen.stop()
        self.assertIn("eth0", gen.setup_error)
        self.assertIn("not permitted", gen.setup_error)
        self.assertEqual(gen.failure(), gen.setup_error)
        self.assertEqual(gen.sent, 0)

    def test_setup_error_bind_closes_socket(self):
        sock = MagicMock()
        sock.bind.side_effect = OSError(19, "No such device")
        gen = xdp_test.TrafficGenerator("eth0")
        with patch("xdp_test.socket") as mock_socket:
            mock_socket.socket.return_value = sock
            gen.start()
            gen.stop()
        self.assertIn("No such device", gen.setup_error)
        sock.close.assert_called_once_with()
        sock.send.assert_not_called()

    def test_sends_frames(self):
        sent = threading.Event()
        sock = self._make_socket(sent_event=sent)
        gen = self._run(sock, sent)
        self.assertIsNone(gen.setup_error)
        self.assertGreaterEqual(gen.sent, 1)
        self.assertEqual(gen.send_errors, 0)
        self.assertIsNone(gen.failure())
        sock.bind.assert_called_once_with(("eth0", 0))
        sock.close.assert_called_once_with()
        frame = sock.send.call_args[0][0]
        self.assertEqual(frame[6:12], self.FRAME_MAC)

    def test_transient_send_errors_are_tolerated(self):
        # e.g. the NIC is reset while the XDP program is attached.
        calls = []
        recovered = threading.Event()

        def send(frame):
            calls.append(frame)
            if len(calls) <= 2:
                raise OSError(100, "Network is down")
            recovered.set()

        gen = self._run(self._make_socket(send=send), recovered)
        self.assertEqual(gen.send_errors, 2)
        self.assertGreaterEqual(gen.sent, 1)
        self.assertIn("Network is down", str(gen.last_send_error))
        self.assertIsNone(gen.failure())

    def test_all_sends_fail(self):
        def send(frame):
            raise OSError(100, "Network is down")

        failed = threading.Event()
        sock = self._make_socket(send=send, sent_event=failed)
        gen = self._run(sock, failed)
        self.assertEqual(gen.sent, 0)
        self.assertGreaterEqual(gen.send_errors, 1)
        message = gen.failure()
        self.assertIn("no traffic could be generated on eth0", message)

    def test_failure_includes_last_error(self):
        gen = xdp_test.TrafficGenerator("eth0")
        gen.last_send_error = OSError(100, "Network is down")
        self.assertIn("Network is down", gen.failure())

    def test_failure_without_traffic_or_error(self):
        gen = xdp_test.TrafficGenerator("eth0")
        self.assertEqual(
            gen.failure(), "no traffic could be generated on eth0"
        )

    def test_stop_without_start(self):
        xdp_test.TrafficGenerator("eth0").stop()


class XdpTestRunnerPairingTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = xdp_test.XdpTestRunner()

    def test_emit_pairing_ring(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.runner.emit_pairing(["end1", "end2", "end3"])
        out = buf.getvalue()
        self.assertIn("source: end1", out)
        self.assertIn("target: end2", out)
        self.assertIn("source: end2", out)
        self.assertIn("target: end3", out)
        self.assertIn("source: end3", out)
        self.assertIn("target: end1", out)

    def test_emit_pairing_single(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.runner.emit_pairing(["end1"])
        self.assertEqual(buf.getvalue(), "")

    def test_emit_pairing_empty(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.runner.emit_pairing([])
        self.assertEqual(buf.getvalue(), "")

    def test_emit_ports(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.runner.emit_ports(["end1", "end2"])
        self.assertEqual(
            buf.getvalue(), "interface: end1\n\ninterface: end2\n\n"
        )

    def test_emit_ports_empty(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.runner.emit_ports([])
        self.assertEqual(buf.getvalue(), "")

    def test_list_interfaces_uses_detector(self):
        detector = MagicMock()
        detector.list_test_interfaces.return_value = ["end1"]
        runner = xdp_test.XdpTestRunner(detector=detector)
        self.assertEqual(runner.list_interfaces(), ["end1"])


class InterfaceDetectorTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.tmp_path = Path(self._tmpdir.name)
        self.detector = xdp_test.InterfaceDetector(sys_net=self.tmp_path)

    def _make_iface(
        self,
        name,
        physical=True,
        link=True,
        wireless=False,
        phy80211=False,
        wwan=False,
        link_type=None,
    ):
        base = self.tmp_path / name
        base.mkdir(parents=True, exist_ok=True)
        if physical:
            (base / "device").symlink_to(self.tmp_path)
        if link:
            (base / "carrier").write_text("1")
        else:
            (base / "carrier").write_text("0")
        if wireless:
            (base / "wireless").mkdir()
        if phy80211:
            (base / "phy80211").mkdir()
        if wwan:
            (base / "uevent").write_text("INTERFACE=wwan0\nDEVTYPE=wwan\n")
        if link_type is not None:
            (base / "type").write_text("{}\n".format(link_type))

    def test_is_physical_ethernet(self):
        self._make_iface("eth0")
        self.assertTrue(self.detector.is_physical_ethernet("eth0"))

    def test_is_physical_ethernet_lo(self):
        self._make_iface("lo")
        self.assertFalse(self.detector.is_physical_ethernet("lo"))

    def test_is_physical_ethernet_virtual(self):
        self._make_iface("docker0", physical=False)
        self.assertFalse(self.detector.is_physical_ethernet("docker0"))

    def test_is_physical_ethernet_wireless(self):
        self._make_iface("wlan0", wireless=True)
        self.assertFalse(self.detector.is_physical_ethernet("wlan0"))

    def test_is_physical_ethernet_phy80211(self):
        self._make_iface("wlan1", phy80211=True)
        self.assertFalse(self.detector.is_physical_ethernet("wlan1"))

    def test_is_physical_ethernet_wwan(self):
        self._make_iface("wwan0", wwan=True, link_type=1)
        self.assertFalse(self.detector.is_physical_ethernet("wwan0"))

    def test_is_physical_ethernet_uevent_not_wwan(self):
        self._make_iface("eth0")
        (self.tmp_path / "eth0" / "uevent").write_text("INTERFACE=eth0\n")
        self.assertTrue(self.detector.is_physical_ethernet("eth0"))

    def test_is_physical_ethernet_type_ether(self):
        self._make_iface("eth0", link_type=1)
        self.assertTrue(self.detector.is_physical_ethernet("eth0"))

    def test_is_physical_ethernet_type_not_ether(self):
        # e.g. ARPHRD_RAWIP (519) used by some modems.
        self._make_iface("wwan1", link_type=519)
        self.assertFalse(self.detector.is_physical_ethernet("wwan1"))

    def test_has_link(self):
        self._make_iface("eth0", link=True)
        self.assertTrue(self.detector.has_link("eth0"))

    def test_has_link_down(self):
        self._make_iface("eth0", link=False)
        self.assertFalse(self.detector.has_link("eth0"))

    def test_list_test_interfaces(self):
        self._make_iface("eth0")
        self._make_iface("eth1")
        self._make_iface("lo")
        self._make_iface("docker0", physical=False)
        self._make_iface("wlan0", wireless=True)
        self._make_iface("wwan0", wwan=True)
        self._make_iface("eth2", link=False)
        self.assertEqual(
            self.detector.list_test_interfaces(), ["eth0", "eth1"]
        )

    def test_list_test_interfaces_natural_order(self):
        for name in ("eth10", "eth2", "eth1"):
            self._make_iface(name)
        self.assertEqual(
            self.detector.list_test_interfaces(), ["eth1", "eth2", "eth10"]
        )


class DefaultRouteTestCase(unittest.TestCase):
    HEADER = (
        "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask"
        "\t\tMTU\tWindow\tIRTT\n"
    )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.route = Path(self._tmpdir.name) / "route"

    def _detector(self):
        return xdp_test.InterfaceDetector(proc_route=self.route)

    def test_default_route_interfaces(self):
        self.route.write_text(
            self.HEADER
            + "end1\t00000000\t0102A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
            + "end1\t0002A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
            + "end2\t00000000\t0102A8C0\t0003\t0\t0\t200\t00000000\t0\t0\t0\n"
        )
        self.assertEqual(
            self._detector().default_route_interfaces(), {"end1", "end2"}
        )

    def test_no_default_route(self):
        self.route.write_text(
            self.HEADER
            + "end1\t0002A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
        )
        self.assertEqual(self._detector().default_route_interfaces(), set())

    def test_route_file_missing(self):
        self.assertEqual(self._detector().default_route_interfaces(), set())


class BuildCommandTestCase(unittest.TestCase):
    def test_basic_actions(self):
        for action in ("drop", "tx", "pass"):
            self.assertEqual(
                xdp_test.XdpBenchRunner.build_command(action, "end2"),
                [
                    "xdp-bench",
                    action,
                    "-m",
                    "native",
                    "-p",
                    "no-touch",
                    "end2",
                ],
            )

    def test_redirect(self):
        self.assertEqual(
            xdp_test.XdpBenchRunner.build_command("redirect", "end2", "end3"),
            ["xdp-bench", "redirect", "-m", "native", "-s", "end2", "end3"],
        )

    def test_redirect_requires_target(self):
        with self.assertRaises(ValueError):
            xdp_test.XdpBenchRunner.build_command("redirect", "end2")

    def test_redirect_cpu(self):
        cmd = xdp_test.XdpBenchRunner.build_command("redirect-cpu", "end2")
        self.assertEqual(cmd[:2], ["xdp-bench", "redirect-cpu"])
        self.assertEqual(cmd[-1], "end2")
        self.assertIn("-e", cmd)
        self.assertEqual(cmd[cmd.index("-p") + 1], "no-touch")
        self.assertEqual(cmd[cmd.index("-c") + 1], "0")

    def test_unknown_action(self):
        with self.assertRaises(ValueError):
            xdp_test.XdpBenchRunner.build_command("bogus", "end2")


class XdpBenchRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = xdp_test.XdpBenchRunner()

    def _run(self, proc, *args, **kwargs):
        buf = io.StringIO()
        with patch.object(
            xdp_test.subprocess, "Popen", return_value=proc
        ), patch.object(xdp_test.time, "sleep"), redirect_stdout(buf):
            result = self.runner.run(*args, **kwargs)
        return result, buf.getvalue()

    def test_run_echoes_command(self):
        proc = FakeProc([("Packets received    : 1\n", None)])
        _, out = self._run(proc, "drop", "end2")
        self.assertIn(
            "Command: xdp-bench drop -m native -p no-touch end2", out
        )

    def test_run_echoes_redirect_command(self):
        proc = FakeProc([("Packets received    : 1\n", None)])
        _, out = self._run(proc, "redirect", "end2", target="end3")
        self.assertIn(
            "Command: xdp-bench redirect -m native -s end2 end3", out
        )

    def test_run_returns_output_and_sends_sigint(self):
        proc = FakeProc([("stats\n", None)], returncode=0)
        (rc, output), _ = self._run(proc, "drop", "end2")
        self.assertEqual((rc, output), (0, "stats\n"))
        self.assertEqual(proc.signals, [xdp_test.signal.SIGINT])
        self.assertFalse(proc.terminated)
        self.assertFalse(proc.killed)

    def test_run_sleeps_for_duration(self):
        runner = xdp_test.XdpBenchRunner(duration=7)
        proc = FakeProc()
        with patch.object(
            xdp_test.subprocess, "Popen", return_value=proc
        ), patch.object(xdp_test.time, "sleep") as sleep, redirect_stdout(
            io.StringIO()
        ):
            runner.run("drop", "end2")
        sleep.assert_called_once_with(7)

    def test_timeout_terminates_and_detaches(self):
        proc = FakeProc([_timeout(), ("partial\n", None)])
        completed = subprocess.CompletedProcess([], 0, stdout="")
        with patch.object(
            xdp_test.subprocess, "run", return_value=completed
        ) as run:
            with self.assertRaises(xdp_test.XdpBenchError) as ctx:
                self._run(proc, "drop", "end2")
        self.assertIn("stopped forcibly", str(ctx.exception))
        self.assertEqual(ctx.exception.output, "partial\n")
        self.assertTrue(proc.terminated)
        self.assertFalse(proc.killed)
        self.assertEqual(
            run.call_args[0][0],
            ["ip", "link", "set", "dev", "end2", "xdp", "off"],
        )

    def test_timeout_after_terminate_kills(self):
        proc = FakeProc([_timeout(), _timeout(), ("late\n", None)])
        completed = subprocess.CompletedProcess([], 0, stdout="")
        with patch.object(xdp_test.subprocess, "run", return_value=completed):
            with self.assertRaises(xdp_test.XdpBenchError) as ctx:
                self._run(proc, "tx", "end2")
        self.assertTrue(proc.terminated)
        self.assertTrue(proc.killed)
        self.assertEqual(ctx.exception.output, "late\n")

    def test_detach_xdp_failure_warns(self):
        completed = subprocess.CompletedProcess([], 2, stdout="boom\n")
        buf = io.StringIO()
        with patch.object(
            xdp_test.subprocess, "run", return_value=completed
        ), redirect_stdout(buf):
            xdp_test.XdpBenchRunner._detach_xdp("end2")
        self.assertIn(
            "Warning: failed to detach XDP from end2", buf.getvalue()
        )
        self.assertIn("boom", buf.getvalue())

    def test_detach_xdp_ip_missing_warns(self):
        buf = io.StringIO()
        with patch.object(
            xdp_test.subprocess, "run", side_effect=FileNotFoundError("ip")
        ), redirect_stdout(buf):
            xdp_test.XdpBenchRunner._detach_xdp("end2")
        self.assertIn("could not run ip", buf.getvalue())

    def test_detach_xdp_success_is_quiet(self):
        completed = subprocess.CompletedProcess([], 0, stdout="")
        buf = io.StringIO()
        with patch.object(
            xdp_test.subprocess, "run", return_value=completed
        ), redirect_stdout(buf):
            xdp_test.XdpBenchRunner._detach_xdp("end2")
        self.assertNotIn("Warning", buf.getvalue())


class RunActionTestCase(unittest.TestCase):
    """XdpTestRunner.run_action with the traffic generator mocked out."""

    DROP_OK = "Packets received    : 13\nRx dropped          : 13\n"

    def setUp(self):
        self.detector = MagicMock()
        self.detector.default_route_interfaces.return_value = set()
        self.bench = MagicMock()
        self.bench.run.return_value = (0, self.DROP_OK)
        self.runner = xdp_test.XdpTestRunner(
            detector=self.detector, bench=self.bench
        )
        self.generator = MagicMock()
        self.generator.setup_error = None
        self.generator.send_errors = 0
        self.generator.failure.return_value = None

    def _run(self, *args, **kwargs):
        buf = io.StringIO()
        with patch(
            "xdp_test.TrafficGenerator", return_value=self.generator
        ) as cls, patch.object(xdp_test.time, "sleep"), redirect_stdout(buf):
            rc = self.runner.run_action(*args, **kwargs)
        self.traffic_cls = cls
        return rc, buf.getvalue()

    def test_success(self):
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 0)
        self.assertIn("Success: all 13 packets dropped at XDP", out)
        self.bench.run.assert_called_once_with("drop", "end2", None)
        self.generator.start.assert_called_once_with()
        self.generator.stop.assert_called_once_with()

    def test_single_port_traffic_from_interface(self):
        self._run("drop", "end2")
        self.traffic_cls.assert_called_once_with("end2")

    def test_redirect_traffic_from_target(self):
        self.bench.run.return_value = (
            0,
            "Packets received    : 11\nPackets transmitted : 11\n",
        )
        rc, _ = self._run("redirect", "end2", "end3")
        self.assertEqual(rc, 0)
        self.traffic_cls.assert_called_once_with("end3")
        self.bench.run.assert_called_once_with("redirect", "end2", "end3")

    def test_not_supported(self):
        self.bench.run.return_value = (1, "Operation not supported\n")
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 1)
        self.assertIn("does not support XDP native mode", out)

    def test_nonzero_exit_status(self):
        self.bench.run.return_value = (3, "something else\n")
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 1)
        self.assertIn("xdp-bench exited with status 3", out)

    def test_errors_reported(self):
        self.bench.run.return_value = (
            0,
            "Summary 3 rx/s 2 err/s\n" + self.DROP_OK,
        )
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 1)
        self.assertIn("Fail: non-zero err/s observed", out)

    def test_checker_failure(self):
        self.bench.run.return_value = (
            0,
            "Packets received    : 0\n",
        )
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 1)
        self.assertIn("Fail: no packets received", out)

    def test_traffic_setup_error_skips_xdp_bench(self):
        self.generator.setup_error = "cannot send traffic on end2: denied"
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 1)
        self.assertIn("Fail: cannot send traffic on end2: denied", out)
        self.bench.run.assert_not_called()
        self.generator.stop.assert_called_once_with()

    def test_traffic_failure_after_run(self):
        self.generator.failure.return_value = "no traffic could be generated"
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 1)
        self.assertIn("Fail: no traffic could be generated", out)

    def test_send_errors_are_noted_but_not_fatal(self):
        self.generator.send_errors = 3
        self.generator.last_send_error = OSError(100, "Network is down")
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 0)
        self.assertIn("Note: 3 frame(s) could not be sent on end2", out)
        self.assertIn("Network is down", out)

    def test_forced_stop_fails(self):
        self.bench.run.side_effect = xdp_test.XdpBenchError(
            "xdp-bench did not exit", "partial output\n"
        )
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 1)
        self.assertIn("partial output", out)
        self.assertIn("Fail: xdp-bench did not exit", out)
        self.generator.stop.assert_called_once_with()

    def test_warns_when_interface_has_default_route(self):
        self.detector.default_route_interfaces.return_value = {"end2"}
        rc, out = self._run("drop", "end2")
        self.assertEqual(rc, 0)
        self.assertIn("Warning: end2 holds the IPv4 default route", out)

    def test_no_warning_without_default_route(self):
        self.detector.default_route_interfaces.return_value = {"end1"}
        _, out = self._run("drop", "end2")
        self.assertNotIn("Warning", out)


class MainTestCase(unittest.TestCase):
    def _main(self, *argv):
        with patch.object(sys, "argv", ["xdp_test.py"] + list(argv)), patch(
            "xdp_test.XdpTestRunner"
        ) as cls:
            self.runner = cls.return_value
            self.runner.list_interfaces.return_value = ["end1", "end2"]
            self.runner.run_action.return_value = 0
            return xdp_test.main()

    def test_list_ports(self):
        self.assertEqual(self._main("--action", "list-ports"), 0)
        self.runner.emit_ports.assert_called_once_with(["end1", "end2"])
        self.runner.run_action.assert_not_called()

    def test_pair_ports(self):
        self.assertEqual(self._main("--action", "pair-ports"), 0)
        self.runner.emit_pairing.assert_called_once_with(["end1", "end2"])
        self.runner.run_action.assert_not_called()

    def test_run_action_returns_status(self):
        self.assertEqual(
            self._main("--action", "drop", "--interface", "end1"), 0
        )
        self.runner.run_action.assert_called_once_with("drop", "end1", None)

    def test_run_action_propagates_failure(self):
        argv = ["xdp_test.py", "--action", "tx", "--interface", "end1"]
        with patch.object(sys, "argv", argv), patch(
            "xdp_test.XdpTestRunner"
        ) as cls:
            cls.return_value.run_action.return_value = 1
            self.assertEqual(xdp_test.main(), 1)

    def test_redirect_passes_target(self):
        self._main(
            "--action",
            "redirect",
            "--interface",
            "end1",
            "--target",
            "end2",
        )
        self.runner.run_action.assert_called_once_with(
            "redirect", "end1", "end2"
        )

    def test_interface_required(self):
        with self.assertRaises(SystemExit) as ctx:
            self._main("--action", "drop")
        self.assertIn("--interface is required", str(ctx.exception))

    def test_target_required_for_redirect(self):
        with self.assertRaises(SystemExit) as ctx:
            self._main("--action", "redirect", "--interface", "end1")
        self.assertIn("--target is required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
