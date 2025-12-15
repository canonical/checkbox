#!/usr/bin/env python3

import unittest
from unittest.mock import patch, call
import subprocess

import suspend_trigger


@patch("suspend_trigger.fwts_test")
@patch("suspend_trigger.time.sleep")
@patch("suspend_trigger.platform.machine")
class TestSuspendTriggerFWTS(unittest.TestCase):

    def test_wait_argument(self, mock_machine, mock_sleep, mock_fwts_test):
        """
        Tests if the --wait argument correctly calls time.sleep.
        """
        mock_machine.return_value = "x86_64"
        suspend_trigger.main(["--wait", "15"])
        mock_sleep.assert_called_once_with(15)
        # Verify that the rest of the script (fwts path) also runs
        self.assertTrue(mock_fwts_test.main.called)

    def test_fwts_path_on_x86_64_with_arguments(
        self, mock_machine, mock_sleep, mock_fwts_test
    ):
        """
        Tests the FWTS code path on x86_64 architecture with custom arguments.
        """
        mock_machine.return_value = "x86_64"

        suspend_trigger.main(["--sleep-delay", "22", "--check-delay", "55"])

        mock_sleep.assert_not_called()
        self.assertTrue(mock_machine.called)
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
        self, mock_machine, mock_sleep, mock_fwts_test
    ):
        """
        Tests the FWTS code path on i386 with no arguments.
        """
        # Mock os.getenv to return the default value passed to it in the script
        mock_machine.return_value = "i386"

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


@patch("suspend_trigger.fwts_test")
@patch("suspend_trigger.subprocess.check_call")
@patch("suspend_trigger.platform.machine")
@patch("os.remove")
@patch("os.path.exists")
class TestSuspendTriggerRTCWake(unittest.TestCase):
    def test_rtcwake_path_success_with_args(
        self,
        mock_exists,
        mock_remove,
        mock_machine,
        mock_check_call,
        mock_fwts_test,
    ):
        """
        Tests the rtcwake/systemctl path on aarch64 with custom arguments.
        """
        mock_machine.return_value = "aarch64"

        suspend_trigger.main(["--sleep-delay", "25", "--rtc-device", "/dev/my_rtc"])

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
            call(expected_rtcwake_cmd),
            call(expected_suspend_cmd),
        ]
        mock_check_call.assert_has_calls(subprocess_calls)
        self.assertEqual(mock_check_call.call_count, 2)

    def test_rtcwake_path_with_defaults(
        self,
        mock_exists,
        mock_remove,
        mock_machine,
        mock_check_call,
        mock_fwts_test,
    ):
        """
        Tests the rtcwake/systemctl path without any argument.
        """
        mock_machine.return_value = "riscv64"

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
            call(expected_rtcwake_cmd),
            call(expected_suspend_cmd),
        ]
        mock_check_call.assert_has_calls(subprocess_calls)

    def test_rtcwake_command_failure(
        self,
        mock_exists,
        mock_remove,
        mock_machine,
        mock_check_call,
        mock_fwts_test,
    ):
        """
        Tests the case where the rtcwake command fails.
        """
        mock_machine.return_value = "aarch64"
        # Simulate a command failure
        error = subprocess.CalledProcessError(
            returncode=1, cmd="rtcwake", output="Error from rtcwake"
        )
        mock_check_call.side_effect = error

        # The script should propagate the exception
        with self.assertRaises(subprocess.CalledProcessError):
            suspend_trigger.main([])

        # Verify that only the first command (rtcwake) was attempted
        self.assertTrue(mock_check_call.called)
        self.assertIn("rtcwake", mock_check_call.call_args[0][0])

    def test_suspend_command_failure(
        self,
        mock_exists,
        mock_remove,
        mock_machine,
        mock_check_call,
        mock_fwts_test,
    ):
        """
        Tests the case where the systemctl suspend command fails.
        """
        mock_machine.return_value = "aarch64"
        suspend_error = subprocess.CalledProcessError(
            returncode=1, cmd="systemctl suspend", output="Error from suspend"
        )
        # The first call (rtcwake) succeeds, the second (suspend) fails.
        mock_check_call.side_effect = [None, suspend_error]

        with self.assertRaises(subprocess.CalledProcessError):
            suspend_trigger.main([])

        # Verify both commands were attempted
        self.assertEqual(mock_check_call.call_count, 2)
        self.assertIn("rtcwake", mock_check_call.call_args_list[0][0][0])
        self.assertIn("systemctl", mock_check_call.call_args_list[1][0][0])

    def test_log_file_removed_if_exists(
        self,
        mock_exists,
        mock_remove,
        mock_machine,
        mock_check_call,
        mock_fwts_test,
    ):
        """
        Tests that /tmp/fwts_results.log is removed if it exists
        after suspend command runs.
        """
        mock_machine.return_value = "aarch64"
        mock_exists.return_value = True  # Simulate file exists
        mock_check_call.side_effect = [None, None]

        suspend_trigger.main([])

        # Verify commands were called
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
        mock_check_call.assert_has_calls(
            [
                call(expected_rtcwake_cmd),
                call(expected_suspend_cmd),
            ]
        )

        # Verify log file existence check and removal
        mock_exists.assert_any_call("/tmp/fwts_results.log")
        mock_remove.assert_called_once_with("/tmp/fwts_results.log")

    def test_log_file_not_removed_if_missing(
        self,
        mock_exists,
        mock_remove,
        mock_machine,
        mock_check_call,
        mock_fwts_test,
    ):
        """
        Tests that /tmp/fwts_results.log is not removed if it does not exist.
        """
        mock_machine.return_value = "aarch64"
        mock_exists.return_value = False  # Simulate file missing
        mock_check_call.side_effect = [None, None]

        suspend_trigger.main([])
        # Verify remove was never called
        mock_remove.assert_not_called()
