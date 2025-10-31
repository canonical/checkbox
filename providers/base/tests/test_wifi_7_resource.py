from unittest.mock import MagicMock, patch, call
from wifi_7_resource import main
import unittest as ut


class TestWifi7Resource(ut.TestCase):

    @patch("builtins.print")
    @patch("os.uname")
    @patch("subprocess.check_output")
    def test_happy_path(
        self,
        mock_check_output: MagicMock,
        mock_os_uname: MagicMock,
        mock_print: MagicMock,
    ):
        mock_check_output.return_value = "\n".join(
            [
                "wpa_supplicant v2.11",
                "Copyright (c) 2003-2022, Jouni Malinen <j@w1.fi> and contributors",  # noqa: E501
            ]
        )
        mock_os_uname.return_value.release = "6.14.0-32-generic"
        calls = [
            call("wpa_supplicant_at_least_2_11: True"),
            call("kernel_at_least_6_14: True"),
        ]
        main()
        mock_print.assert_has_calls(calls)

    @patch("builtins.print")
    @patch("os.uname")
    @patch("subprocess.check_output")
    def test_wpasupplicant_version_too_old(
        self,
        mock_check_output: MagicMock,
        mock_os_uname: MagicMock,
        mock_print: MagicMock,
    ):
        mock_check_output.return_value = "\n".join(
            [
                "wpa_supplicant v2.4",
                "Copyright (c) 2003-2015, Jouni Malinen <j@w1.fi> and contributors",  # noqa: E501
            ]
        )
        mock_os_uname.return_value.release = "6.14.0-1012-oem"
        main()
        calls = [
            call("wpa_supplicant_at_least_2_11: False"),
            call("kernel_at_least_6_14: True"),
        ]
        mock_print.assert_has_calls(calls)

    @patch("builtins.print")
    @patch("os.uname")
    @patch("subprocess.check_output")
    def test_kernel_version_too_old(
        self,
        mock_check_output: MagicMock,
        mock_os_uname: MagicMock,
        mock_print: MagicMock,
    ):
        mock_check_output.return_value = "\n".join(
            [
                "wpa_supplicant v2.11",
                "Copyright (c) 2003-2015, Jouni Malinen <j@w1.fi> and contributors",  # noqa: E501
            ]
        )
        mock_os_uname.return_value.release = "6.11.0-1011-oem"
        main()
        calls = [
            call("wpa_supplicant_at_least_2_11: True"),
            call("kernel_at_least_6_14: False"),
        ]
        mock_print.assert_has_calls(calls)


if __name__ == "__main__":
    ut.main()
