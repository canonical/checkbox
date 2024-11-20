#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Eugene Wu <eugene.wu@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import netifaces
import requests
from wol_client import (
    request,
    post,
    check_wakeup,
    get_ip_mac,
    set_rtc_wake,
    s3_or_s5_system,
    bring_up_system,
    write_timestamp,
    parse_args,
    main,
)


class TestRequestFunction(unittest.TestCase):
    @patch("wol_client.Session")
    @patch("wol_client.Retry")
    def test_request(self, mock_retry, mock_session):
        mock_retry.return_value = MagicMock()
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = (
            mock_session_instance
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session_instance.request.return_value = mock_response

        url = "https://example.com/api"
        method = "POST"

        response = request(method, url, retry=2, json={"key": "value"})

        mock_retry.assert_called_once_with(total=2)
        mock_session.assert_called_once()
        mock_session_instance.mount.assert_any_call(
            "https://", unittest.mock.ANY
        )
        mock_session_instance.mount.assert_any_call(
            "http://", unittest.mock.ANY
        )
        mock_session_instance.request.assert_called_once_with(
            method=method, url=url, json={"key": "value"}
        )
        self.assertEqual(response.status_code, 200)


class TestPostFunction(unittest.TestCase):
    @patch("wol_client.request")
    def test_post(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        url = "https://example.com/api"
        data = {"key": "value"}

        response = post(url, data=data)

        mock_request.assert_called_once_with(
            "post", url, data=data, json=None, retry=3
        )
        self.assertEqual(response.status_code, 200)


class TestCheckWakeup(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="enabled\n")
    def test_wakeup_enabled(self, mock_file):
        self.assertTrue(check_wakeup("eth0"))
        mock_file.assert_called_with(
            "/sys/class/net/eth0/device/power/wakeup", "r"
        )

    @patch("builtins.open", new_callable=mock_open, read_data="disabled\n")
    def test_wakeup_disabled(self, mock_file):
        self.assertFalse(check_wakeup("eth0"))
        mock_file.assert_called_with(
            "/sys/class/net/eth0/device/power/wakeup", "r"
        )

    @patch("builtins.open", new_callable=mock_open, read_data="unknown\n")
    def test_wakeup_unexpected_status(self, mock_file):
        with self.assertRaises(ValueError) as context:
            check_wakeup("eth0")
        self.assertEqual(
            str(context.exception), "Unexpected wakeup status: unknown"
        )

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_interface_not_found(self, mock_file):
        with self.assertRaises(FileNotFoundError) as context:
            check_wakeup("nonexistent")
        self.assertEqual(
            str(context.exception),
            "The network interface nonexistent does not exist.",
        )

    @patch("builtins.open", side_effect=Exception("Unexpected error"))
    def test_unexpected_error(self, mock_file):
        with self.assertRaises(Exception) as context:
            check_wakeup("eth0")
        self.assertEqual(str(context.exception), "Unexpected error")


class TestGetIpMacFunction(unittest.TestCase):
    @patch("wol_client.netifaces.ifaddresses")
    def test_get_ip_mac_success(self, mock_ifaddresses):
        # Mock the return value of netifaces.ifaddresses
        mock_ifaddresses.return_value = {
            netifaces.AF_LINK: [{"addr": "00:11:22:33:44:55"}],
            netifaces.AF_INET: [{"addr": "192.168.1.10"}],
        }

        ip, mac = get_ip_mac("eth0")

        self.assertEqual(ip, "192.168.1.10")
        self.assertEqual(mac, "00:11:22:33:44:55")

    @patch("wol_client.netifaces.ifaddresses")
    def test_get_ip_mac_no_ip(self, mock_ifaddresses):
        # Mock the return value of netifaces.ifaddresses (no AF_INET)
        mock_ifaddresses.return_value = {
            netifaces.AF_LINK: [{"addr": "00:11:22:33:44:55"}],
            # No AF_INET key to simulate no IP address
        }

        ip, mac = get_ip_mac("eth0")

        self.assertIsNone(ip)  # No IP address should be returned
        self.assertEqual(mac, "00:11:22:33:44:55")

    @patch("wol_client.netifaces.ifaddresses")
    def test_get_ip_mac_interface_not_found(self, mock_ifaddresses):
        # Simulate a missing network interface by raising an exception
        mock_ifaddresses.side_effect = ValueError("No interface found")

        # Call the function and check for system exit
        with self.assertRaises(SystemExit):
            get_ip_mac("nonexistent_interface")


class TestSetRTCWake(unittest.TestCase):

    @patch("wol_client.subprocess.check_output")
    def test_set_rtc_wake_success(self, mock_check_output):
        """Test successful RTC wake time setting."""
        expected_wake_time = 180
        mock_check_output.return_value = b""  # Simulate successful execution
        set_rtc_wake(expected_wake_time)
        mock_check_output.assert_called_once_with(
            ["rtcwake", "-m", "no", "-s", str(expected_wake_time)], stderr=-2
        )

    @patch("wol_client.subprocess.check_output")
    def test_set_rtc_wake_failed(self, mock_check_output):
        """Test handling of subprocess.CalledProcessError."""
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "rtcwake", output=b"Error message"
        )
        with self.assertRaises(SystemExit) as cm:
            set_rtc_wake(60)
        self.assertEqual(
            str(cm.exception), "Failed to set RTC wake: Error message"
        )

    @patch("wol_client.subprocess.check_output")
    def test_set_rtc_wake_unexpected_error(self, mock_check_output):
        """Test handling of unexpected exceptions."""
        mock_check_output.side_effect = Exception("Unexpected error")
        with self.assertRaises(SystemExit) as cm:
            set_rtc_wake(60)
        self.assertEqual(
            str(cm.exception), "An unexpected error occurred: Unexpected error"
        )


class TestS3OrS5System(unittest.TestCase):

    @patch("wol_client.subprocess.check_output")
    def test_s3_success(self, mock_check_output):
        mock_check_output.return_value = b""
        s3_or_s5_system("s3")
        mock_check_output.assert_called_once_with(
            ["systemctl", "suspend"], stderr=subprocess.STDOUT
        )

    @patch("wol_client.subprocess.check_output")
    def test_s5_success(self, mock_check_output):
        mock_check_output.return_value = b""
        s3_or_s5_system("s5")
        mock_check_output.assert_called_once_with(
            ["systemctl", "poweroff"], stderr=subprocess.STDOUT
        )

    def test_invalid_type(self):
        with self.assertRaises(RuntimeError) as cm:
            s3_or_s5_system("invalid")
        self.assertEqual(
            str(cm.exception),
            "Error: type should be s3 or s5(provided: invalid)",
        )

    @patch("wol_client.subprocess.check_output")
    def test_subprocess_error(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "cmd", output="Failed"
        )
        with self.assertRaises(RuntimeError) as cm:
            s3_or_s5_system("s3")
        self.assertIn("Try to enter s3 failed", str(cm.exception))


class TestBringUpSystem(unittest.TestCase):

    @patch("wol_client.set_rtc_wake")
    def test_bring_up_system_rtc(self, mock_set_rtc_wake):
        bring_up_system("rtc", "10:00")
        mock_set_rtc_wake.assert_called_once_with("10:00")

    def test_bring_up_system_invalid_way(self):
        with self.assertRaises(SystemExit) as cm:
            bring_up_system("invalid", "10:00")
        self.assertEqual(
            str(cm.exception),
            "we don't have the way invalid to bring up the system,"
            "Some error happened.",
        )


class TestWriteTimestamp(unittest.TestCase):
    @patch("builtins.open")
    def test_write_timestamp(self, mock_file_open):
        """Tests if the timestamp is correctly written to the file."""
        write_timestamp("/tmp/timestamp_file")
        mock_file_open.assert_called_once_with("/tmp/timestamp_file", "w")
        handle = mock_file_open.return_value.__enter__.return_value
        handle.write.assert_called_once()
        handle.flush.assert_called_once()


class TestParseArgs(unittest.TestCase):
    def test_parse_all_arguments(self):
        """Tests parsing all arguments."""
        args = [
            "--interface",
            "enp0s31f6",
            "--target",
            "192.168.1.10",
            "--delay",
            "120",
            "--retry",
            "3",
            "--waketype",
            "m",
            "--powertype",
            "s5",
            "--timestamp_file",
            "/tmp/time_stamp",
        ]
        parsed_args = parse_args(args)
        self.assertEqual(parsed_args.interface, "enp0s31f6")
        self.assertEqual(parsed_args.target, "192.168.1.10")
        self.assertEqual(parsed_args.delay, 120)
        self.assertEqual(parsed_args.retry, 3)
        self.assertEqual(parsed_args.waketype, "m")
        self.assertEqual(parsed_args.powertype, "s5")
        self.assertEqual(parsed_args.timestamp_file, "/tmp/time_stamp")

    def test_parse_required_arguments(self):
        """Tests parsing required arguments."""
        args = ["--interface", "eth0", "--target", "192.168.1.10"]
        parsed_args = parse_args(args)
        self.assertEqual(parsed_args.interface, "eth0")
        self.assertEqual(parsed_args.target, "192.168.1.10")
        self.assertEqual(parsed_args.delay, 60)  # Default value
        self.assertEqual(parsed_args.retry, 3)  # Default value
        self.assertEqual(parsed_args.waketype, "g")  # Default value
        self.assertIsNone(parsed_args.powertype)


def create_mock_args():
    return MagicMock(
        delay=10,
        retry=3,
        interface="eth0",
        target="192.168.1.1",
        waketype="magic_packet",
        timestamp_file="/tmp/timestamp",
        powertype="s3",
    )


def create_mock_response(status_code=200, result="success"):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = {"result": result}
    return mock_response


class TestMainFunction(unittest.TestCase):

    @patch("wol_client.s3_or_s5_system")
    @patch("wol_client.write_timestamp")
    @patch("wol_client.bring_up_system")
    @patch("wol_client.post")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.parse_args")
    def test_main_success(
        self,
        mock_parse_args,
        mock_get_ip_mac,
        mock_check_wakeup,
        mock_post,
        mock_bring_up_system,
        mock_write_timestamp,
        mock_s3_or_s5_system,
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_get_ip_mac.return_value = ("192.168.1.100", "00:11:22:33:44:55")
        mock_check_wakeup.return_value = True
        mock_post.return_value = create_mock_response()

        main()

        mock_get_ip_mac.assert_called_once_with("eth0")
        mock_post.assert_called_once_with(
            "http://192.168.1.1",
            json={
                "DUT_MAC": "00:11:22:33:44:55",
                "DUT_IP": "192.168.1.100",
                "delay": 10,
                "retry_times": 3,
                "wake_type": "magic_packet",
            },
            retry=3,
        )
        mock_bring_up_system.assert_called_once_with("rtc", 10 * 3 * 2)
        mock_write_timestamp.assert_called_once_with("/tmp/timestamp")
        mock_s3_or_s5_system.assert_called_once_with("s3")

    @patch("wol_client.post")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.parse_args")
    def test_main_ip_none(
        self, mock_parse_args, mock_check_wakeup, mock_get_ip_mac, mock_post
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_get_ip_mac.return_value = (None, "00:11:22:33:44:55")
        mock_check_wakeup.return_value = True

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception), "Error: failed to get the ip address."
        )

    @patch("wol_client.post")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.parse_args")
    def test_main_post_failure(
        self, mock_parse_args, mock_check_wakeup, mock_get_ip_mac, mock_post
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_get_ip_mac.return_value = ("192.168.1.100", "00:11:22:33:44:55")
        mock_post.return_value = create_mock_response(
            status_code=400, result="failure"
        )
        mock_check_wakeup.return_value = True

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertIn("get the wrong response: failure", str(cm.exception))

    @patch("wol_client.post")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.parse_args")
    def test_main_request_exception(
        self, mock_parse_args, mock_check_wakeup, mock_get_ip_mac, mock_post
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_check_wakeup.return_value = True
        mock_get_ip_mac.return_value = ("192.168.1.100", "00:11:22:33:44:55")
        mock_post.side_effect = requests.exceptions.RequestException(
            "Simulated error"
        )

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(str(cm.exception), "Request error: Simulated error")

    @patch("wol_client.post")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.parse_args")
    def test_main_checkwakeup_disable(
        self, mock_parse_args, mock_check_wakeup, mock_get_ip_mac, mock_post
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_check_wakeup.return_value = False
        mock_get_ip_mac.return_value = ("192.168.1.100", "00:11:22:33:44:55")
        mock_post.return_value = create_mock_response()

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertIn("wake-on-LAN of eth0 is disabled!", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
