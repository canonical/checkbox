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
from unittest.mock import patch, MagicMock, mock_open, Mock
import subprocess
import json
import struct

from wol_client import (
    send_request_to_wol_server,
    check_wakeup,
    get_ip_mac,
    set_rtc_wake,
    s3_or_s5_system,
    bring_up_system,
    write_timestamp,
    parse_args,
    main,
)


class TestSendRequestToWolServerFunction(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_send_request_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"result": "success"}
        ).encode("utf-8")
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        mock_urlopen.return_value.__enter__.return_value = mock_response

        url = "http://192.168.1.1"
        data = {"key": "value"}

        result = send_request_to_wol_server(url, data)

        self.assertIsNone(result)

    @patch("urllib.request.urlopen")
    def test_send_request_failed_status_not_200(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"result": "failure"}
        ).encode("utf-8")
        mock_response.getcode.return_value = 400
        mock_urlopen.return_value = mock_response
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(SystemExit):
            send_request_to_wol_server(
                "http://192.168.1.1", data={"key": "value"}
            )

    @patch("urllib.request.urlopen")
    def test_send_request_failed_response_not_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"result": "failure"}
        ).encode("utf-8")
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(SystemExit):
            send_request_to_wol_server(
                "http://192.168.1.1", data={"key": "value"}
            )

    @patch("urllib.request.urlopen")
    def test_send_request_unexpected_exception(self, mock_urlopen):
        # Mock an unexpected exception
        mock_urlopen.side_effect = Exception("Unexpected error")

        with self.assertRaises(SystemExit):
            send_request_to_wol_server(
                "http://192.168.1.1", data={"key": "value"}
            )

        self.assertEqual(mock_urlopen.call_count, 3)


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


class TestGetIPMac(unittest.TestCase):
    @patch("socket.socket")
    @patch("fcntl.ioctl")
    def test_get_ip_mac_success(self, mock_ioctl, mock_socket):
        # Mock data
        interface = "eth0"
        mock_ip = b"\xc0\xa8\x00\x01"  # 192.168.0.1
        mock_mac = b"\x00\x0c)\x85\xac\x0e"  # 00:0c:29:85:ac:0e

        # Configure the mock objects
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance

        def ioctl_side_effect(fd, request, arg):
            if request == 0x8915:
                return b"\x00" * 20 + mock_ip + b"\x00" * (256 - 24)
            elif request == 0x8927:
                return b"\x00" * 18 + mock_mac + b"\x00" * (256 - 24)
            # raise IOError("Invalid request")

        mock_ioctl.side_effect = ioctl_side_effect

        ip_address, mac_address = get_ip_mac(interface)

        self.assertEqual(ip_address, "192.168.0.1")
        self.assertEqual(mac_address, "00:0c:29:85:ac:0e")

    @patch("socket.socket")
    @patch("fcntl.ioctl")
    def test_get_ip_address_failure(self, mock_ioctl, mock_socket):
        # Mock data
        interface = "eth0"
        mock_mac = b"\x00\x0c)\x85\xac\x0e"  # 00:0c:29:85:ac:0e

        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance

        def ioctl_side_effect(fd, request, arg):
            if request == 0x8915:
                raise IOError("IP address retrieval failed")
            elif request == 0x8927:
                # return struct.pack('256s', b'\x00' * 18) + mock_mac
                return b"\x00" * 18 + mock_mac + b"\x00" * (256 - 24)

        mock_ioctl.side_effect = ioctl_side_effect

        ip_address, mac_address = get_ip_mac(interface)

        self.assertIsNone(ip_address)
        self.assertEqual(mac_address, "00:0c:29:85:ac:0e")

    @patch("socket.socket")
    @patch("fcntl.ioctl")
    def test_get_mac_address_failure(self, mock_ioctl, mock_socket):
        interface = "eth0"
        mock_ip = b"\xc0\xa8\x00\x01"  # 192.168.0.1

        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance

        def ioctl_side_effect(fd, request, arg):
            if request == 0x8915:
                return struct.pack("256s", b"\x00" * 16) + mock_ip
            elif request == 0x8927:
                raise IOError("MAC address retrieval failed")

        mock_ioctl.side_effect = ioctl_side_effect

        with self.assertRaises(SystemExit):
            get_ip_mac(interface)


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
    @patch("wol_client.send_request_to_wol_server")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.parse_args")
    def test_main_success(
        self,
        mock_parse_args,
        mock_get_ip_mac,
        mock_check_wakeup,
        mock_send_request_to_wol_server,
        mock_bring_up_system,
        mock_write_timestamp,
        mock_s3_or_s5_system,
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_get_ip_mac.return_value = ("192.168.1.100", "00:11:22:33:44:55")
        mock_check_wakeup.return_value = True
        mock_send_request_to_wol_server.return_value = create_mock_response()

        main()

        mock_get_ip_mac.assert_called_once_with("eth0")
        mock_send_request_to_wol_server.assert_called_once_with(
            "http://192.168.1.1",
            data={
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

    @patch("wol_client.send_request_to_wol_server")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.parse_args")
    def test_main_ip_none(
        self,
        mock_parse_args,
        mock_check_wakeup,
        mock_get_ip_mac,
        mock_send_request_to_wol_server,
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_get_ip_mac.return_value = (None, "00:11:22:33:44:55")
        mock_check_wakeup.return_value = True

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception), "Error: failed to get the ip address."
        )

    @patch("wol_client.send_request_to_wol_server")
    @patch("wol_client.get_ip_mac")
    @patch("wol_client.check_wakeup")
    @patch("wol_client.parse_args")
    def test_main_checkwakeup_disable(
        self,
        mock_parse_args,
        mock_check_wakeup,
        mock_get_ip_mac,
        mock_send_request_to_wol_server,
    ):
        mock_parse_args.return_value = create_mock_args()
        mock_check_wakeup.return_value = False
        mock_get_ip_mac.return_value = ("192.168.1.100", "00:11:22:33:44:55")
        mock_send_request_to_wol_server.return_value = create_mock_response()

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertIn("wake-on-LAN of eth0 is disabled!", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
