import unittest
from textwrap import dedent
from unittest.mock import patch

import failed_service_check


class FailedServiceCheckTests(unittest.TestCase):

    @patch("failed_service_check.run")
    @patch("failed_service_check.check_output")
    @patch(
        "failed_service_check.os.getenv",
        return_value="fwupd-refresh.service",
    )
    def test_main_filters_blacklist_and_reports_failed_service(
        self, mock_getenv, mock_check_output, mock_run
    ):
        mock_check_output.return_value = dedent("""
            plymouth-start.service loaded failed failed Show Plymouth Boot Screen
            network-manager-wait-online.service loaded failed failed Wait for Network
            fwupd-refresh.service loaded failed failed Refresh fwupd metadata
            """).strip()

        with patch("builtins.print") as mock_print, self.assertRaises(
            SystemExit
        ) as raised:
            failed_service_check.main()

        self.assertEqual(raised.exception.code, 1)
        mock_run.assert_called_once_with(
            [
                "journalctl",
                "--no-pager",
                "-n",
                "50",
                "-u",
                "network-manager-wait-online.service",
            ],
            stdin=failed_service_check.DEVNULL,
        )
        mock_print.assert_any_call("Found 1 failed units")
        mock_print.assert_any_call("Ignoring failing services (blacklisted): ")
