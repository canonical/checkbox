#!/usr/bin/env python3

import unittest
from unittest.mock import patch, call
import subprocess

import suspend_trigger


@patch("suspend_trigger.fwts_test")
@patch("suspend_trigger.time.sleep")
@patch("suspend_trigger.platform.machine")
@patch("suspend_trigger.os.getenv")
class TestSuspendTriggerFWTS(unittest.TestCase):

    def test_wait_argument(
        self, mock_getenv, mock_machine, mock_sleep, mock_fwts_test
    ):
        """
        Tests if the --wait argument correctly calls time.sleep.
        """
        mock_getenv.return_value = "30"
        mock_machine.return_value = "x86_64"
        suspend_trigger.main(["--wait", "15"])
        mock_sleep.assert_called_once_with(15)
        # Verify that the rest of the script (fwts path) also runs
        self.assertTrue(mock_fwts_test.main.called)

    def test_fwts_path_on_x86_64_with_env_vars(
        self, mock_getenv, mock_machine, mock_sleep, mock_fwts_test
    ):
        """
        Tests the FWTS code path on x86_64 architecture with custom environment variables.
        """
        mock_machine.return_value = "x86_64"

        # Mock os.getenv to return specific values for the test
        def getenv_side_effect(key, default=None):
            env_vars = {
                "STRESS_S3_WAIT_DELAY": "55",
                "STRESS_S3_SLEEP_DELAY": "22",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        suspend_trigger.main([])

        mock_sleep.assert_not_called()
        mock_machine.assert_called_once()
        expected_fwts_args = [
            "-f",
            "none",
            "-s",
            "s3",
            "--s3-device-check",
            "--s3-device-check-delay",
            "55",
            "--s3-sleep-delay",
            "22",
        ]
        mock_fwts_test.main.assert_called_once_with(expected_fwts_args)

    def test_fwts_path_on_i386_with_defaults(
        self, mock_getenv, mock_machine, mock_sleep, mock_fwts_test
    ):
        """
        Tests the FWTS code path on i386 with default environment variables.
        """
        # Mock os.getenv to return the default value passed to it in the script
        mock_machine.return_value = "i386"
        mock_getenv.side_effect = lambda key, default: default

        suspend_trigger.main([])

        mock_sleep.assert_not_called()
        expected_fwts_args = [
            "-f",
            "none",
            "-s",
            "s3",
            "--s3-device-check",
            "--s3-device-check-delay",
            "45",  # Default from script
            "--s3-sleep-delay",
            "30",  # Default from script
        ]
        mock_fwts_test.main.assert_called_once_with(expected_fwts_args)
        # Verify that os.getenv was called correctly
        getenv_calls = [
            call("STRESS_S3_WAIT_DELAY", "45"),
            call("STRESS_S3_SLEEP_DELAY", "30"),
        ]
        mock_getenv.assert_has_calls(getenv_calls, any_order=True)


@patch("suspend_trigger.fwts_test")
@patch("suspend_trigger.subprocess.check_output")
@patch("suspend_trigger.platform.machine")
@patch("suspend_trigger.os.getenv")
class TestSuspendTriggerRTCWake(unittest.TestCase):
    def test_rtcwake_path_success_with_env_vars(
        self, mock_getenv, mock_machine, mock_check_output, mock_fwts_test
    ):
        """
        Tests the rtcwake/systemctl path on aarch64 with custom environment variables.
        """
        mock_machine.return_value = "aarch64"

        def getenv_side_effect(key, default=None):
            env_vars = {
                "STRESS_S3_SLEEP_DELAY": "25",
                "RTC_DEVICE_FILE": "/dev/my_rtc",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect
        mock_check_output.return_value = "Mocked subprocess output"

        suspend_trigger.main([])

        self.assertFalse(mock_fwts_test.main.called)
        expected_rtcwake_cmd = [
            "rtcwake",
            "--verbose",
            "--device",
            "/dev/my_rtc",
            "--mode",
            "no",
            "--seconds",
            "25",
        ]
        expected_suspend_cmd = ["systemctl", "suspend"]
        subprocess_calls = [
            call(
                expected_rtcwake_cmd,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            ),
            call(
                expected_suspend_cmd,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            ),
        ]
        mock_check_output.assert_has_calls(subprocess_calls)
        self.assertEqual(mock_check_output.call_count, 2)

    def test_rtcwake_path_with_defaults(
        self, mock_getenv, mock_machine, mock_check_output, mock_fwts_test
    ):
        """
        Tests the rtcwake/systemctl path with default environment variables.
        """
        mock_machine.return_value = "riscv64"
        mock_getenv.side_effect = lambda key, default: default
        mock_check_output.return_value = "Mocked output"

        suspend_trigger.main([])

        expected_rtcwake_cmd = [
            "rtcwake",
            "--verbose",
            "--device",
            "/dev/rtc0",
            "--mode",
            "no",
            "--seconds",
            "30",
        ]
        expected_suspend_cmd = ["systemctl", "suspend"]
        subprocess_calls = [
            call(
                expected_rtcwake_cmd,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            ),
            call(
                expected_suspend_cmd,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            ),
        ]
        mock_check_output.assert_has_calls(subprocess_calls)

    def test_rtcwake_command_failure(
        self, mock_getenv, mock_machine, mock_check_output, mock_fwts_test
    ):
        """
        Tests the case where the rtcwake command fails.
        """
        mock_machine.return_value = "aarch64"
        mock_getenv.side_effect = lambda key, default: default
        # Simulate a command failure
        error = subprocess.CalledProcessError(
            returncode=1, cmd="rtcwake", output="Error from rtcwake"
        )
        mock_check_output.side_effect = error

        # The script should propagate the exception
        with self.assertRaises(subprocess.CalledProcessError):
            suspend_trigger.main([])

        # Verify that only the first command (rtcwake) was attempted
        mock_check_output.assert_called_once()
        self.assertIn("rtcwake", mock_check_output.call_args[0][0])

    def test_suspend_command_failure(
        self, mock_getenv, mock_machine, mock_check_output, mock_fwts_test
    ):
        """
        Tests the case where the systemctl suspend command fails.
        """
        mock_machine.return_value = "aarch64"
        mock_getenv.side_effect = lambda key, default: default
        suspend_error = subprocess.CalledProcessError(
            returncode=1, cmd="systemctl suspend", output="Error from suspend"
        )
        # The first call (rtcwake) succeeds, the second (suspend) fails.
        mock_check_output.side_effect = ["rtcwake success", suspend_error]

        with self.assertRaises(subprocess.CalledProcessError):
            suspend_trigger.main([])

        # Verify both commands were attempted
        self.assertEqual(mock_check_output.call_count, 2)
        self.assertIn("rtcwake", mock_check_output.call_args_list[0][0][0])
        self.assertIn("systemctl", mock_check_output.call_args_list[1][0][0])
