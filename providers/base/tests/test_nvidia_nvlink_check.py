#!/usr/bin/env python3
import unittest
from unittest.mock import patch
from nvidia_nvlink_check import check_nvlink_status


class TestNvidiaVlinkCheck(unittest.TestCase):

    @patch("nvidia_nvlink_check.subprocess.check_output")
    def test_empty_output(self, mock_check_output):
        """Test when nvidia-smi nvlink --status returns empty string

        Driver 580 behavior on unsupported devices returns nothing
        """
        mock_check_output.return_value = ""
        result = check_nvlink_status()
        self.assertFalse(result)

    @patch("nvidia_nvlink_check.subprocess.check_output")
    def test_unsupported_device_does_not_have(self, mock_check_output):
        """Test when device explicitly states lack of support

        Driver 595 behavior on unsupported devices with exact case
        """
        output = (
            "GPU 0: Quadro RTX 4000 with Max-Q Design "
            "(UUID: GPU-3193a2da-ea05-d9e8-dd6d-24fa7a760595)\n"
            "Device does not have or support Nvlink"
        )
        mock_check_output.return_value = output
        result = check_nvlink_status()
        self.assertFalse(result)

    @patch("nvidia_nvlink_check.subprocess.check_output")
    def test_unsupported_device_not_supported(self, mock_check_output):
        """Test when device output contains "Not supported" with capital N"""
        output = "GPU 0: Some Device\n" "Not supported"
        mock_check_output.return_value = output
        result = check_nvlink_status()
        self.assertFalse(result)

    @patch("nvidia_nvlink_check.subprocess.check_output")
    def test_nvlink_present_with_link_keyword(self, mock_check_output):
        """Test when output contains "Link" with capital L"""
        output = "  Link 0: active"
        mock_check_output.return_value = output
        result = check_nvlink_status()
        self.assertTrue(result)

    @patch("nvidia_nvlink_check.subprocess.check_output")
    def test_nvlink_present_multiple_links(self, mock_check_output):
        """Test when output contains multiple Link entries"""
        output = (
            "GPU 0: Tesla V100\n"
            "    Link 0: 50 GB/s\n"
            "    Link 1: 50 GB/s\n"
            "    Link 2: 50 GB/s\n"
            "    Link 3: 50 GB/s"
        )
        mock_check_output.return_value = output
        result = check_nvlink_status()
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
