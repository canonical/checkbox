import unittest
import argparse
from unittest.mock import patch, Mock, MagicMock
from watchdog_config_test import (
    watchdog_argparse,
    get_systemd_wdt_usec,
    watchdog_service_check,
    check_timeout,
    check_service,
    main,
)


class TestWatchdogConfigTest(unittest.TestCase):

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(check_time=True, check_service=False),
    )
    def test_check_time_argument(self, mock_parse_args):
        result = watchdog_argparse()
        self.assertTrue(result.check_time)
        self.assertFalse(result.check_service)

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(check_time=False, check_service=True),
    )
    def test_check_service_argument(self, mock_parse_args):
        result = watchdog_argparse()
        self.assertFalse(result.check_time)
        self.assertTrue(result.check_service)

    @patch("watchdog_config_test.subprocess.check_output")
    def test_get_systemd_wdt_usec_success(self, mock_check_output):
        # Mock subprocess.check_output to return a mock result
        mock_check_output.return_value = "RuntimeWatchdogUSec=1000000\n"

        # Call the function under test
        result = get_systemd_wdt_usec()

        # Assert that subprocess.check_output was called
        # with the correct arguments
        mock_check_output.assert_called_once_with(
            ["systemctl", "show", "-p", "RuntimeWatchdogUSec"],
            universal_newlines=True,
        )

        # Assert that the correct value was returned
        self.assertEqual(result, "1000000")

    @patch("watchdog_config_test.subprocess.check_output")
    def test_get_systemd_wdt_usec_exception(self, mock_check_output):
        # Mock subprocess.check_output to raise an exception
        mock_check_output.side_effect = Exception("Something went wrong")

        # Call the function under test
        with self.assertRaises(SystemExit):
            get_systemd_wdt_usec()

    @patch("watchdog_config_test.subprocess.check_output")
    def test_get_systemd_wdt_usec_no_result(self, mock_check_output):
        # Mock subprocess.check_output to return an empty result
        mock_check_output.return_value = ""

        # Call the function under test
        with self.assertRaises(SystemExit):
            get_systemd_wdt_usec()

    @patch("watchdog_config_test.subprocess.run")
    def test_watchdog_service_check_active(self, mock_subprocess_run):
        mock_process = Mock(returncode=0)
        mock_subprocess_run.return_value = mock_process

        result = watchdog_service_check()

        mock_subprocess_run.assert_called_once_with(
            ["systemctl", "is-active", "watchdog.service", "--quiet"]
        )

        self.assertTrue(result)

    @patch("watchdog_config_test.subprocess.run")
    def test_watchdog_service_check_inactive(self, mock_subprocess_run):
        mock_process = Mock(returncode=1)
        mock_subprocess_run.return_value = mock_process

        result = watchdog_service_check()

        mock_subprocess_run.assert_called_once_with(
            ["systemctl", "is-active", "watchdog.service", "--quiet"]
        )

        self.assertFalse(result)

    @patch("watchdog_config_test.subprocess.run")
    def test_watchdog_service_check_exception(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = Exception("Something went wrong")

        with self.assertRaises(SystemExit):
            watchdog_service_check()

    @patch("builtins.print")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.get_series")
    def test_check_timeout_classic_jammy(
        self, mock_series, mock_get_wdt_sec, mock_print
    ):
        mock_series.return_value = "22.04"
        mock_get_wdt_sec.return_value = "30"

        check_timeout()
        mock_series.assert_called_with()
        self.assertEqual(mock_print.call_count, 1)

    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.get_series")
    def test_check_timeout_core_bionic(
        self, mock_series, mock_on_uc, mock_get_wdt_sec
    ):
        mock_series.return_value = "18"
        mock_get_wdt_sec.return_value = "0"
        mock_on_uc.return_value = True

        with self.assertRaises(SystemExit):
            check_timeout()
        mock_series.assert_called_with()
        mock_on_uc.assert_called_with()

    @patch("builtins.print")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.get_series")
    def test_check_timeout_classic_bionic_passed(
        self, mock_series, mock_on_uc, mock_get_wdt_sec, mock_print
    ):
        mock_series.return_value = "18.04"
        mock_get_wdt_sec.return_value = "0"
        mock_on_uc.return_value = False

        check_timeout()
        mock_series.assert_called_with()
        mock_on_uc.assert_called_with()
        self.assertEqual(mock_print.call_count, 1)

    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.get_series")
    def test_check_timeout_classic_bionic_failed(
        self, mock_series, mock_on_uc, mock_get_wdt_sec
    ):
        mock_series.return_value = "18.04"
        mock_get_wdt_sec.return_value = "30"
        mock_on_uc.return_value = False

        with self.assertRaises(SystemExit):
            check_timeout()
        mock_series.assert_called_with()
        mock_on_uc.assert_called_with()

    @patch("builtins.print")
    @patch("watchdog_config_test.watchdog_service_check")
    @patch("watchdog_config_test.get_series")
    def test_check_service_classic_jammy(
        self, mock_series, mock_service, mock_print
    ):
        mock_series.return_value = "22.04"
        mock_service.return_value = False

        check_service()
        mock_series.assert_called_with()
        mock_service.assert_called_with()
        self.assertEqual(mock_print.call_count, 1)

    @patch("watchdog_config_test.watchdog_service_check")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.get_series")
    def test_check_service_core_bionic(
        self, mock_series, mock_on_uc, mock_service
    ):
        mock_series.return_value = "18"
        mock_service.return_value = True
        mock_on_uc.return_value = True

        with self.assertRaises(SystemExit):
            check_service()
        mock_series.assert_called_with()
        mock_on_uc.assert_called_with()

    @patch("builtins.print")
    @patch("watchdog_config_test.watchdog_service_check")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.get_series")
    def test_check_service_classic_bionic_passed(
        self, mock_series, mock_on_uc, mock_service, mock_print
    ):
        mock_series.return_value = "18.04"
        mock_service.return_value = True
        mock_on_uc.return_value = False

        check_service()
        mock_series.assert_called_with()
        mock_on_uc.assert_called_with()
        self.assertEqual(mock_print.call_count, 1)

    @patch("watchdog_config_test.watchdog_service_check")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.get_series")
    def test_check_service_classic_bionic_failed(
        self, mock_series, mock_on_uc, mock_service
    ):
        mock_series.return_value = "18.04"
        mock_service.return_value = False
        mock_on_uc.return_value = False

        with self.assertRaises(SystemExit):
            check_service()
        mock_series.assert_called_with()
        mock_on_uc.assert_called_with()

    @patch("watchdog_config_test.check_timeout")
    @patch("watchdog_config_test.watchdog_argparse")
    def test_main_check_time(self, mock_argparse, mock_check_timeout):

        mock_args = MagicMock()
        mock_args.check_time = True
        mock_argparse.return_value = mock_args

        main()
        mock_check_timeout.assert_called_once_with()

    @patch("watchdog_config_test.check_service")
    @patch("watchdog_config_test.watchdog_argparse")
    def test_main_check_service(self, mock_argparse, mock_check_service):
        mock_args = MagicMock()
        mock_args.check_time = False
        mock_args.check_service = True
        mock_argparse.return_value = mock_args

        main()
        mock_check_service.assert_called_once_with()

    @patch("watchdog_config_test.check_timeout")
    @patch("watchdog_config_test.check_service")
    @patch("watchdog_config_test.watchdog_argparse")
    def test_main_invalid_argument(
        self, mock_argparse, mock_check_service, mock_check_timeout
    ):
        mock_args = MagicMock()
        mock_args.check_time = False
        mock_args.check_service = False
        mock_argparse.return_value = mock_args

        with self.assertRaises(SystemExit):
            main()

        mock_check_service.assert_not_called()
        mock_check_timeout.assert_not_called()
