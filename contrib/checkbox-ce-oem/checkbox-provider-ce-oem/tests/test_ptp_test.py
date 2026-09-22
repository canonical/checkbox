import os
import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

import ptp_test


def _proc(returncode=0, stdout="", stderr=""):
    return CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class TestPtp4lVersion(unittest.TestCase):
    @patch("ptp_test.subprocess.run", return_value=_proc(stdout="4.2\n"))
    def test_parses_major_version(self, _):
        self.assertEqual(ptp_test.ptp4l_major_version(), 4)

    @patch("ptp_test.subprocess.run", return_value=_proc(stdout="3.1.1\n"))
    def test_parses_three_part_version(self, _):
        self.assertEqual(ptp_test.ptp4l_major_version(), 3)

    @patch("ptp_test.subprocess.run", return_value=_proc(stdout="garbage"))
    def test_unparsable_version_is_none(self, _):
        self.assertIsNone(ptp_test.ptp4l_major_version())


class TestBuildPtp4lArgs(unittest.TestCase):
    def test_defaults_keep_the_historical_command_line(self):
        # transportSpecific defaults to 1 so platforms that relied on the
        # old hard-coded value (NXP, TI) keep their behaviour.
        self.assertEqual(
            ptp_test.build_ptp4l_args("eth0", {}, ptp4l_major=3),
            [
                "-i",
                "eth0",
                "-m",
                "-s",
                "--network_transport=L2",
                "--tx_timestamp_timeout=5",
                "--transportSpecific=1",
            ],
        )

    def test_transport_specific_from_environment(self):
        # A Realtek RTL8126 (r8126) only hardware-timestamps
        # transportSpecific=0 frames, so the launcher can turn the nibble off.
        args = ptp_test.build_ptp4l_args(
            "eth0", {"PTP4L_TRANSPORT_SPECIFIC": "0"}, ptp4l_major=3
        )
        self.assertIn("--transportSpecific=0", args)
        self.assertNotIn("--transportSpecific=1", args)

    def test_invalid_transport_specific_is_rejected(self):
        with self.assertRaises(SystemExit):
            ptp_test.build_ptp4l_args(
                "eth0", {"PTP4L_TRANSPORT_SPECIFIC": "2"}, ptp4l_major=3
            )

    def test_minor_version_added_on_ptp4l_4(self):
        args = ptp_test.build_ptp4l_args(
            "eth0", {"PTP4L_PTP_MINOR_VERSION": "1"}, ptp4l_major=4
        )
        self.assertIn("--ptp_minor_version=1", args)

    def test_minor_version_skipped_on_older_ptp4l(self):
        args = ptp_test.build_ptp4l_args(
            "eth0", {"PTP4L_PTP_MINOR_VERSION": "1"}, ptp4l_major=3
        )
        self.assertNotIn("--ptp_minor_version=1", args)

    def test_delay_mechanism_unset_keeps_ptp4l_default(self):
        args = ptp_test.build_ptp4l_args("eth0", {}, ptp4l_major=3)
        self.assertFalse(any(a.startswith("--delay_mechanism") for a in args))

    def test_delay_mechanism_p2p_for_gptp(self):
        args = ptp_test.build_ptp4l_args(
            "eth0",
            {"PTP4L_TRANSPORT_SPECIFIC": "1", "PTP4L_DELAY_MECHANISM": "p2p"},
            ptp4l_major=3,
        )
        self.assertIn("--delay_mechanism=P2P", args)
        self.assertIn("--transportSpecific=1", args)

    def test_delay_mechanism_e2e_explicit(self):
        args = ptp_test.build_ptp4l_args(
            "eth0", {"PTP4L_DELAY_MECHANISM": "E2E"}, ptp4l_major=3
        )
        self.assertIn("--delay_mechanism=E2E", args)

    def test_invalid_delay_mechanism_is_rejected(self):
        with self.assertRaises(SystemExit):
            ptp_test.build_ptp4l_args(
                "eth0", {"PTP4L_DELAY_MECHANISM": "AUTO"}, ptp4l_major=3
            )


PTP4L_SYNCED = """\
ptp4l[259.664]: selected best master clock d8860b.fffe.302283
ptp4l[259.664]: port 1: LISTENING to UNCALIBRATED on RS_SLAVE
ptp4l[261.664]: port 1: UNCALIBRATED to SLAVE on MASTER_CLOCK_SELECTED
ptp4l[262.665]: rms  243 max  406 freq -12171 +/- 335 delay  6835 +/-   0
ptp4l[263.665]: rms  322 max  592 freq -12006 +/- 419 delay  6828 +/-   0
ptp4l[264.665]: rms  263 max  436 freq -12058 +/- 361 delay  6685 +/-   0
"""

PTP4L_NO_TX_TIMESTAMP = """\
ptp4l[259.664]: selected best master clock d8860b.fffe.302283
ptp4l[259.664]: port 1: LISTENING to UNCALIBRATED on RS_SLAVE
ptp4l[260.949]: timed out while polling for tx timestamp
ptp4l[260.950]: port 1: send delay request failed
ptp4l[260.950]: port 1: UNCALIBRATED to FAULTY on FAULT_DETECTED
"""

# P2P through a bridge: the peer-delay exchange never completes, no error
PTP4L_P2P_STUCK = """\
ptp4l[259.664]: port 1: new foreign master d8860b.fffe.302283-1
ptp4l[259.664]: selected best master clock d8860b.fffe.302283
ptp4l[259.664]: port 1: LISTENING to UNCALIBRATED on RS_SLAVE
"""


class TestRmsValues(unittest.TestCase):
    def test_extracts_rms_from_last_lines(self):
        self.assertEqual(
            ptp_test.rms_values(PTP4L_SYNCED, last=5), [243, 322, 263]
        )

    def test_no_rms_when_never_synced(self):
        self.assertEqual(ptp_test.rms_values(PTP4L_NO_TX_TIMESTAMP), [])

    def test_only_the_last_n_lines_are_considered(self):
        self.assertEqual(ptp_test.rms_values(PTP4L_SYNCED, last=1), [263])


@patch.dict(os.environ, {}, clear=True)
class TestRunSyncTest(unittest.TestCase):
    @patch("ptp_test.ptp4l_major_version", return_value=3)
    @patch("ptp_test.run_ptp4l", return_value=PTP4L_SYNCED)
    def test_pass_when_rms_within_limit(self, *_):
        self.assertEqual(ptp_test.run_sync_test("eth0", 30, 1000), 0)

    @patch("ptp_test.ptp4l_major_version", return_value=3)
    @patch("ptp_test.run_ptp4l", return_value=PTP4L_SYNCED)
    def test_fail_when_rms_too_big(self, *_):
        self.assertEqual(ptp_test.run_sync_test("eth0", 30, 200), 1)

    @patch("ptp_test.ptp4l_major_version", return_value=3)
    @patch("ptp_test.run_ptp4l", return_value=PTP4L_NO_TX_TIMESTAMP)
    def test_fail_and_hint_when_no_rms(self, *_):
        with patch("builtins.print") as mock_print:
            self.assertEqual(ptp_test.run_sync_test("eth0", 30, 1000), 1)
        printed = " ".join(str(c.args[0]) for c in mock_print.call_args_list)
        self.assertIn("TX timestamp", printed)
        self.assertIn("PTP4L_TRANSPORT_SPECIFIC", printed)

    @patch("ptp_test.ptp4l_major_version", return_value=3)
    @patch("ptp_test.run_ptp4l", return_value=PTP4L_P2P_STUCK)
    def test_p2p_hint_when_peer_delay_never_completes(self, *_):
        with patch.dict(os.environ, {"PTP4L_DELAY_MECHANISM": "P2P"}):
            with patch("builtins.print") as mock_print:
                self.assertEqual(ptp_test.run_sync_test("eth0", 30, 1000), 1)
        printed = " ".join(str(c.args[0]) for c in mock_print.call_args_list)
        self.assertIn("01:80:C2:00:00:0E", printed)

    @patch("ptp_test.ptp4l_major_version", return_value=3)
    @patch("ptp_test.run_ptp4l", return_value=PTP4L_SYNCED)
    def test_passes_environment_to_arg_builder(self, mock_run, _):
        with patch.dict(os.environ, {"PTP4L_TRANSPORT_SPECIFIC": "0"}):
            ptp_test.run_sync_test("eth0", 30, 1000)
        self.assertIn("--transportSpecific=0", mock_run.call_args.args[0])


class TestMain(unittest.TestCase):
    @patch("ptp_test.run_sync_test", return_value=0)
    def test_sync_subcommand(self, mock_sync):
        with self.assertRaises(SystemExit) as cm:
            ptp_test.main(
                ["sync", "eth0", "--duration", "20", "--rms-max", "500"]
            )
        self.assertEqual(cm.exception.code, 0)
        mock_sync.assert_called_once_with("eth0", 20, 500)


if __name__ == "__main__":
    unittest.main()
