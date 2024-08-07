#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock
from wifi_interface_mode import (
    run_command,
    get_interfaces,
    get_wiphy_info,
    print_supported_modes,
    main,
)


class TestWiFiFunctions(unittest.TestCase):
    @patch("subprocess.run")
    def test_run_command_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=b"output", stderr=b"", returncode=0
        )
        result = run_command(["echo", "hello"])
        self.assertEqual(result, "output")

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run):
        mock_run.side_effect = Exception("Command failed")
        with self.assertRaises(SystemError) as context:
            run_command(["echo", "hello"])

        self.assertIn(
            "An unexpected error occurred: Command failed",
            str(context.exception),
        )

    @patch("wifi_interface_mode.run_command")
    def test_get_interfaces(self, mock_run_command):
        mock_run_command.return_value = """
        phy#0
            Interface wlan0
        phy#1
            Interface wlan1
        """
        expected = [("0", "wlan0"), ("1", "wlan1")]
        result = get_interfaces()
        self.assertEqual(result, expected)

    @patch("wifi_interface_mode.run_command")
    def test_get_interfaces_no_wifi_interface(self, mock_run_command):
        mock_run_command.return_value = ""

        with self.assertRaises(SystemExit) as cm:
            get_interfaces()

        self.assertEqual(cm.exception.code, 0)

    @patch("wifi_interface_mode.run_command")
    def test_get_wiphy_info_with_one_phy(self, mock_run_command):
        mock_run_command.return_value = """Wiphy phy0
        Supported interface modes:
        * managed
        * AP/VLAN
        * monitor
        """
        expected = [
            (
                "0",
                ["managed", "AP/VLAN", "monitor"],
            ),
        ]
        result = get_wiphy_info()
        self.assertEqual(result, expected)

    @patch("wifi_interface_mode.run_command")
    def test_get_wiphy_info_with_phy_start_with_mwi(self, mock_run_command):
        mock_run_command.return_value = """Wiphy mwiphy0
        Supported interface modes:
        * managed
        * AP/VLAN
        * monitor
        """
        expected = [
            (
                "0",
                ["managed", "AP/VLAN", "monitor"],
            ),
        ]
        result = get_wiphy_info()
        self.assertEqual(result, expected)

    @patch("wifi_interface_mode.run_command")
    def test_get_wiphy_info_with_two_phy(self, mock_run_command):
        mock_run_command.return_value = """Wiphy phy0
        Supported interface modes:
        * managed
        * AP/VLAN
        * monitor
        Wiphy phy1
        Supported interface modes:
        * managed
        * AP/VLAN
        * P2P-client
        """
        expected = [
            (
                "0",
                ["managed", "AP/VLAN", "monitor"],
            ),
            (
                "1",
                ["managed", "AP/VLAN", "P2P-client"],
            ),
        ]
        result = get_wiphy_info()
        self.assertEqual(result, expected)

    @patch("wifi_interface_mode.get_interfaces")
    @patch("wifi_interface_mode.get_wiphy_info")
    def test_print_supported_modes(
        self, mock_get_wiphy_info, mock_get_interfaces
    ):
        # Mock the return values
        mock_get_interfaces.return_value = [("0", "wlan0"), ("1", "wlan1")]
        mock_get_wiphy_info.return_value = [
            ("0", ["IBSS", "AP/VLAN"]),
            ("1", ["AP", "P2P-client"]),
        ]
        # Mock print to capture output
        with patch("builtins.print") as mock_print:
            print_supported_modes()
            expected_output = [
                "wlan0_IBSS: supported",
                "wlan0_AP/VLAN: supported",
                "wlan1_AP: supported",
                "wlan1_P2P-client: supported",
            ]
            for output in expected_output:
                mock_print.assert_any_call(output)


if __name__ == "__main__":
    unittest.main()
