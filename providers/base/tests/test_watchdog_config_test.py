import unittest
import argparse
from unittest.mock import patch, Mock, MagicMock
from watchdog_config_test import (
    watchdog_argparse,
    get_systemd_wdt_usec,
    watchdog_service_check,
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
        # Mock subprocess.run to return a process with returncode 0 (active)
        mock_process = Mock(returncode=0)
        mock_subprocess_run.return_value = mock_process

        # Call the function under test
        result = watchdog_service_check()

        # Assert that subprocess.run was called with the correct arguments
        mock_subprocess_run.assert_called_once_with(
            ["systemctl", "is-active", "watchdog.service", "--quiet"]
        )

        # Assert that the correct value was returned
        self.assertTrue(result)

    @patch("watchdog_config_test.subprocess.run")
    def test_watchdog_service_check_inactive(self, mock_subprocess_run):
        # Mock subprocess.run to return a process with returncode 1 (inactive)
        mock_process = Mock(returncode=1)
        mock_subprocess_run.return_value = mock_process

        # Call the function under test
        result = watchdog_service_check()

        # Assert that subprocess.run was called with the correct arguments
        mock_subprocess_run.assert_called_once_with(
            ["systemctl", "is-active", "watchdog.service", "--quiet"]
        )

        # Assert that the correct value was returned
        self.assertFalse(result)

    @patch("watchdog_config_test.subprocess.run")
    def test_watchdog_service_check_exception(self, mock_subprocess_run):
        # Mock subprocess.run to raise an exception
        mock_subprocess_run.side_effect = Exception("Something went wrong")

        # Call the function under test
        with self.assertRaises(SystemExit):
            watchdog_service_check()

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_time_and_service(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_systemd_wdt_usec,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = True
        mock_args.check_service = True
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "20.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock get_systemd_wdt_usec
        mock_get_systemd_wdt_usec.return_value = "1000000"

        # Mock watchdog_service_check
        mock_watchdog_service_check.return_value = False

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()

        # Assert that the expected messages are printed
        mock_print.assert_any_call(
            "systemd watchdog enabled, reset timeout: 1000000"
        )
        mock_print.assert_any_call("watchdog.service is not active")

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_time_ubuntucore(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_systemd_wdt_usec,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = True
        mock_args.check_service = False
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_systemd_wdt_usec
        mock_get_systemd_wdt_usec.return_value = 1000000

        # Mock get_series
        mock_get_series.return_value = "18.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = True
        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()

        # Assert that the expected messages are printed
        mock_print.assert_any_call(
            "systemd watchdog enabled, reset timeout: 1000000"
        )

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_time_not_active(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_systemd_wdt_usec,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = True
        mock_args.check_service = False
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "20.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock get_systemd_wdt_usec
        mock_get_systemd_wdt_usec.return_value = "0"

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()

        # Assert that the expected message is printed
        mock_print.assert_any_call(
            "systemd watchdog should be enabled but reset timeout: 0"
        )

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_time_and_systemd_wdt_configured(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_systemd_wdt_usec,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = True
        mock_args.check_service = False
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "20.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock get_systemd_wdt_usec
        mock_get_systemd_wdt_usec.return_value = "1000000"

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()
        # Assert that the expected messages are printed
        mock_print.assert_any_call(
            "systemd watchdog enabled, reset timeout: 1000000"
        )

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_time_and_watchdog_config_ready(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_systemd_wdt_usec,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = True
        mock_args.check_service = False
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "18.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock get_systemd_wdt_usec
        mock_get_systemd_wdt_usec.return_value = "0"

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()
        # Assert that the expected messages are printed
        mock_print.assert_any_call("systemd watchdog disabled")

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.get_systemd_wdt_usec")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_time_is_systemd_wdt_configured(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_systemd_wdt_usec,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = True
        mock_args.check_service = False
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "18.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock get_systemd_wdt_usec
        mock_get_systemd_wdt_usec.return_value = "1000000"

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()
        # Assert that the expected messages are printed
        mock_print.assert_any_call(
            "systemd watchdog should not be enabled but reset timeout: 1000000"
        )

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_service_ubuntucore_not_active(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = False
        mock_args.check_service = True
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "20.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock watchdog_service_check
        mock_watchdog_service_check.return_value = False

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()

        # Assert that the expected message is printed
        mock_print.assert_any_call("watchdog.service is not active")

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_service_ubuntucore_is_wdt_service_configured(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = False
        mock_args.check_service = True
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "20.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock watchdog_service_check
        mock_watchdog_service_check.return_value = True

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()

        # Assert that the expected message is printed
        mock_print.assert_any_call(
            "found unexpected active watchdog.service unit"
        )

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_service_active(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = False
        mock_args.check_service = True
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "18.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock watchdog_service_check
        mock_watchdog_service_check.return_value = True

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()

        # Assert that the expected message is printed
        mock_print.assert_any_call("watchdog.service is active")

    @patch("watchdog_config_test.watchdog_argparse")
    @patch("watchdog_config_test.get_series")
    @patch("watchdog_config_test.on_ubuntucore")
    @patch("watchdog_config_test.watchdog_service_check")
    def test_main_check_service_is_wdt_service_configured(
        self,
        mock_watchdog_service_check,
        mock_on_ubuntucore,
        mock_get_series,
        mock_watchdog_argparse,
    ):
        # Mock arguments
        mock_args = MagicMock()
        mock_args.check_time = False
        mock_args.check_service = True
        mock_watchdog_argparse.return_value = mock_args

        # Mock get_series
        mock_get_series.return_value = "18.04"

        # Mock on_ubuntucore
        mock_on_ubuntucore.return_value = False

        # Mock watchdog_service_check
        mock_watchdog_service_check.return_value = False

        # Call the function under test
        with patch("builtins.print") as mock_print:
            main()

        # Assert that the expected message is printed
        mock_print.assert_any_call(
            "watchdog.service unit does not report as active"
        )
