import subprocess as sp
import unittest
from unittest.mock import MagicMock, call, patch

import network_ntp_chrony_test


class ChronyTests(unittest.TestCase):
    @patch("network_ntp_chrony_test.sp.run")
    def test_reports_active_service(self, run_mock):
        run_mock.return_value = MagicMock(returncode=0)

        self.assertTrue(network_ntp_chrony_test.is_chrony_active())
        run_mock.assert_called_once_with(
            ["systemctl", "is-active", "--quiet", "chrony.service"]
        )

    @patch("network_ntp_chrony_test.sp.run")
    def test_reports_inactive_service(self, run_mock):
        run_mock.return_value = MagicMock(returncode=3)

        self.assertFalse(network_ntp_chrony_test.is_chrony_active())

    @patch("network_ntp_chrony_test.time.strftime")
    @patch("network_ntp_chrony_test.time.localtime")
    @patch("network_ntp_chrony_test.sp.check_output")
    def test_skews_time_and_clears_manual_time(
        self, check_output_mock, localtime_mock, strftime_mock
    ):
        strftime_mock.return_value = "2026-09-01 10:00:00"

        network_ntp_chrony_test.skew_time(3600.0)

        localtime_mock.assert_called_once_with(0.0)
        self.assertEqual(
            check_output_mock.call_args_list,
            [
                call(
                    ["chronyc", "manual", "on"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "settime", "2026-09-01 10:00:00"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "-a", "makestep"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "manual", "reset"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "manual", "off"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
            ],
        )

    @patch("network_ntp_chrony_test.time.strftime")
    @patch("network_ntp_chrony_test.time.localtime")
    @patch("network_ntp_chrony_test.sp.check_output")
    def test_clears_manual_time_after_failure(
        self, check_output_mock, localtime_mock, strftime_mock
    ):
        strftime_mock.return_value = "2026-09-01 10:00:00"
        check_output_mock.side_effect = [
            "",
            sp.CalledProcessError(1, "chronyc settime"),
            "",
            "",
        ]

        with self.assertRaises(sp.CalledProcessError):
            network_ntp_chrony_test.skew_time(3600.0)

        self.assertEqual(
            check_output_mock.call_args_list[-2:],
            [
                call(
                    ["chronyc", "manual", "reset"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "manual", "off"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
            ],
        )

    @patch("network_ntp_chrony_test.sp.check_output")
    def test_synchronizes_with_configured_sources(self, check_output_mock):
        network_ntp_chrony_test.sync_with_chrony(60)

        self.assertEqual(
            check_output_mock.call_args_list,
            [
                call(
                    ["chronyc", "online"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "makestep", "0.1", "1"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "burst", "1/4"],
                    stderr=sp.STDOUT,
                    text=True,
                ),
                call(
                    ["chronyc", "waitsync", "60", "0.1", "0.0", "1"],
                    stderr=sp.STDOUT,
                    text=True,
                    timeout=60,
                ),
            ],
        )


class ArgumentTests(unittest.TestCase):
    def test_parses_timeout_and_debug(self):
        args = network_ntp_chrony_test.parse_args(
            ["--timeout", "120", "--debug"]
        )

        self.assertEqual(args.timeout, 120)
        self.assertTrue(args.debug)


class MainTests(unittest.TestCase):
    @patch("network_ntp_chrony_test.os.geteuid", return_value=1)
    def test_requires_root(self, geteuid_mock):
        self.assertEqual(network_ntp_chrony_test.main([]), 1)

    @patch("network_ntp_chrony_test.is_chrony_active", return_value=False)
    @patch("network_ntp_chrony_test.os.geteuid", return_value=0)
    def test_requires_active_chrony(self, geteuid_mock, active_mock):
        self.assertEqual(network_ntp_chrony_test.main([]), 1)

    @patch("network_ntp_chrony_test.time")
    @patch("network_ntp_chrony_test.sync_with_chrony")
    @patch("network_ntp_chrony_test.skew_time")
    @patch("network_ntp_chrony_test.is_chrony_active", return_value=True)
    @patch("network_ntp_chrony_test.os.geteuid", return_value=0)
    def test_synchronizes_clock(
        self,
        geteuid_mock,
        active_mock,
        skew_mock,
        sync_mock,
        time_mock,
    ):
        time_mock.time.side_effect = [1000.0, 1060.0]
        time_mock.strftime.return_value = "time"

        self.assertEqual(network_ntp_chrony_test.main([]), 0)
        skew_mock.assert_called_once_with(1000.0)
        sync_mock.assert_called_once_with(
            network_ntp_chrony_test.DEFAULT_TIMEOUT
        )

    @patch("network_ntp_chrony_test.time")
    @patch("network_ntp_chrony_test.sync_with_chrony")
    @patch("network_ntp_chrony_test.skew_time")
    @patch("network_ntp_chrony_test.is_chrony_active", return_value=True)
    @patch("network_ntp_chrony_test.os.geteuid", return_value=0)
    def test_fails_when_clock_is_not_restored(
        self,
        geteuid_mock,
        active_mock,
        skew_mock,
        sync_mock,
        time_mock,
    ):
        time_mock.time.side_effect = [1000.0, 999.0]
        time_mock.strftime.return_value = "time"

        self.assertEqual(network_ntp_chrony_test.main([]), 1)

    @patch("network_ntp_chrony_test.time")
    @patch(
        "network_ntp_chrony_test.skew_time",
        side_effect=sp.CalledProcessError(
            1, "chronyc", output="501 Not authorised\n"
        ),
    )
    @patch("network_ntp_chrony_test.is_chrony_active", return_value=True)
    @patch("network_ntp_chrony_test.os.geteuid", return_value=0)
    def test_reports_subprocess_failure(
        self,
        geteuid_mock,
        active_mock,
        skew_mock,
        time_mock,
    ):
        time_mock.time.return_value = 1000.0
        time_mock.strftime.return_value = "time"

        with self.assertLogs(
            network_ntp_chrony_test.logger, level="ERROR"
        ) as log:
            self.assertEqual(network_ntp_chrony_test.main([]), 1)

        self.assertIn("501 Not authorised", log.output[0])


if __name__ == "__main__":
    unittest.main()
