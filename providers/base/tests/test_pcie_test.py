#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#

import logging
import unittest
from unittest import mock

from pcie_test import PCIeTester, _run_command, init_logger, main


class TestPCIeTester(unittest.TestCase):
    """
    Unit tests for pcie_test script
    """

    def setUp(self):
        """Set up test fixtures"""
        self.tester = PCIeTester()

    @mock.patch("pcie_test.subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution"""
        mock_result = mock.Mock()
        mock_result.stdout = "Test output"
        mock_run.return_value = mock_result

        result = _run_command(["lspci"])
        self.assertEqual(result, "Test output")
        self.assertEqual(mock_run.call_count, 1)

    @mock.patch("pcie_test.subprocess.run")
    def test_run_command_file_not_found(self, mock_run):
        """Test command execution when lspci is not installed"""
        mock_run.side_effect = FileNotFoundError()

        with self.assertRaises(RuntimeError) as cm:
            _run_command(["lspci"])
        self.assertIn("command not found", str(cm.exception))

    @mock.patch("pcie_test.subprocess.run")
    def test_run_command_called_process_error(self, mock_run):
        """Test command execution failure"""
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["lspci"], stderr="Error message"
        )

        with self.assertRaises(RuntimeError) as cm:
            _run_command(["lspci"])
        self.assertIn("Error executing command", str(cm.exception))

    def test_parse_link_info_valid(self):
        """Test parsing valid LnkCap/LnkSta lines"""
        line = "LnkCap: Speed 8GT/s, Width x16"
        speed, width = self.tester._parse_link_info(line)
        self.assertEqual(speed, "8GT/s")
        self.assertEqual(width, "x16")

    def test_parse_link_info_invalid(self):
        """Test parsing lines without speed/width info"""
        line = "Some random line without link info"
        speed, width = self.tester._parse_link_info(line)
        self.assertIsNone(speed)
        self.assertIsNone(width)

    @mock.patch("pcie_test._run_command")
    def test_list_resources_success(self, mock_run_cmd):
        """Test listing PCIe resources successfully"""
        mock_run_cmd.return_value = (
            "00:00.0 Host bridge: Intel Corporation\n"
            "01:00.0 VGA compatible controller: NVIDIA Corporation"
        )

        with mock.patch("builtins.print") as mock_print:
            result = self.tester.list_resources()
            self.assertEqual(result, 0)
            # Verify print was called
            self.assertTrue(mock_print.called)

    @mock.patch("pcie_test._run_command")
    def test_list_resources_no_devices(self, mock_run_cmd):
        """Test listing PCIe resources with no devices"""
        mock_run_cmd.return_value = ""

        with mock.patch("builtins.print"):
            result = self.tester.list_resources()
            self.assertEqual(result, 0)

    @mock.patch("pcie_test._run_command")
    def test_list_resources_command_error(self, mock_run_cmd):
        """Test listing PCIe resources when lspci fails"""
        mock_run_cmd.side_effect = RuntimeError("lspci failed")

        with mock.patch("builtins.print"):
            result = self.tester.list_resources()
            self.assertEqual(result, 1)

    @mock.patch("pcie_test._run_command")
    def test_check_link_state_match(self, mock_run_cmd):
        """Test check_link_state when LnkCap matches LnkSta"""
        mock_run_cmd.return_value = (
            "LnkCap: Speed 8GT/s, Width x16\n"
            "LnkSta: Speed 8GT/s, Width x16\n"
        )

        result = self.tester.check_link_state("00:00.0", force=False)
        self.assertEqual(result, 0)

    @mock.patch("pcie_test._run_command")
    def test_check_link_state_mismatch(self, mock_run_cmd):
        """Test check_link_state when LnkCap doesn't match LnkSta"""
        mock_run_cmd.return_value = (
            "LnkCap: Speed 8GT/s, Width x16\n"
            "LnkSta: Speed 5GT/s, Width x8\n"
        )

        result = self.tester.check_link_state("00:00.0", force=False)
        self.assertEqual(result, 1)

    @mock.patch("pcie_test._run_command")
    def test_check_link_state_no_link_info_without_force(self, mock_run_cmd):
        """Test check_link_state with no LnkCap/LnkSta, no --force"""
        mock_run_cmd.return_value = "Some output without link info\n"

        result = self.tester.check_link_state("00:00.0", force=False)
        self.assertEqual(result, 0)  # Should skip

    @mock.patch("pcie_test._run_command")
    def test_check_link_state_no_link_info_with_force(self, mock_run_cmd):
        """Test check_link_state with no LnkCap/LnkSta, with --force"""
        mock_run_cmd.return_value = "Some output without link info\n"

        result = self.tester.check_link_state("00:00.0", force=True)
        self.assertEqual(result, 1)  # Should fail

    @mock.patch("pcie_test._run_command")
    def test_check_link_state_only_cap_found(self, mock_run_cmd):
        """Test check_link_state when only LnkCap is found"""
        mock_run_cmd.return_value = "LnkCap: Speed 8GT/s, Width x16\n"

        result = self.tester.check_link_state("00:00.0", force=False)
        self.assertEqual(result, 1)  # Error state

    @mock.patch("pcie_test._run_command")
    def test_check_link_state_only_sta_found(self, mock_run_cmd):
        """Test check_link_state when only LnkSta is found"""
        mock_run_cmd.return_value = "LnkSta: Speed 8GT/s, Width x16\n"

        result = self.tester.check_link_state("00:00.0", force=False)
        self.assertEqual(result, 1)  # Error state

    @mock.patch("pcie_test._run_command")
    def test_check_link_state_command_error(self, mock_run_cmd):
        """Test check_link_state when _run_command fails"""
        mock_run_cmd.side_effect = RuntimeError("Command failed")

        result = self.tester.check_link_state("00:00.0", force=False)
        self.assertEqual(result, 1)

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_state_not_supported_without_force(self, mock_run_cmd):
        """Test check_aspm_state when ASPM not in LnkCap, no --force"""
        mock_run_cmd.return_value = "LnkCap: Speed 8GT/s, Width x16\n"

        result = self.tester.check_aspm_state("00:00.0", force=False)
        self.assertEqual(result, 0)  # Should pass

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_state_not_supported_with_force(self, mock_run_cmd):
        """Test check_aspm_state when ASPM not in LnkCap, with --force"""
        mock_run_cmd.return_value = "LnkCap: Speed 8GT/s, Width x16\n"

        result = self.tester.check_aspm_state("00:00.0", force=True)
        self.assertEqual(result, 1)  # Should fail

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_state_disabled(self, mock_run_cmd):
        """Test check_aspm_state when ASPM is supported but disabled"""
        mock_run_cmd.return_value = (
            "LnkCap: ASPM L0s L1, Speed 8GT/s, Width x16\n"
            "LnkCtl: ASPM Disabled\n"
        )

        result = self.tester.check_aspm_state("00:00.0", force=False)
        self.assertEqual(result, 1)  # Should fail

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_state_enabled(self, mock_run_cmd):
        """Test check_aspm_state when ASPM is supported and enabled"""
        mock_run_cmd.return_value = (
            "LnkCap: ASPM L0s L1, Speed 8GT/s, Width x16\n"
            "LnkCtl: ASPM L0s L1 Enabled\n"
        )

        result = self.tester.check_aspm_state("00:00.0", force=False)
        self.assertEqual(result, 0)  # Should pass

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_no_lnkcap(self, mock_run_cmd):
        """Test check_aspm_state when no LnkCap is found"""
        mock_run_cmd.return_value = "Some output without LnkCap\n"

        result = self.tester.check_aspm_state("00:00.0", force=False)
        self.assertEqual(result, 0)  # Should skip

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_no_lnkcap_with_force(self, mock_run_cmd):
        """Test check_aspm_state when no LnkCap with --force"""
        mock_run_cmd.return_value = "Some output without LnkCap\n"

        result = self.tester.check_aspm_state("00:00.0", force=True)
        self.assertEqual(result, 1)  # Should fail

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_no_lnkctl_with_support(self, mock_run_cmd):
        """Test check_aspm_state when ASPM supported but no LnkCtl"""
        mock_run_cmd.return_value = (
            "LnkCap: ASPM L0s L1, Speed 8GT/s, Width x16\n"
        )

        result = self.tester.check_aspm_state("00:00.0", force=False)
        self.assertEqual(result, 1)  # Should fail

    @mock.patch("pcie_test._run_command")
    def test_check_aspm_command_error(self, mock_run_cmd):
        """Test check_aspm_state when _run_command fails"""
        mock_run_cmd.side_effect = RuntimeError("Command failed")

        result = self.tester.check_aspm_state("00:00.0", force=False)
        self.assertEqual(result, 1)


class TestInitLogger(unittest.TestCase):
    """Test the init_logger function"""

    def test_init_logger(self):
        """Test that init_logger creates a logger"""
        logger = init_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger.level, logging.INFO)


class TestMain(unittest.TestCase):
    """Test the main function"""

    @mock.patch("pcie_test.sys.exit")
    @mock.patch("pcie_test.init_logger")
    @mock.patch.object(PCIeTester, "list_resources")
    @mock.patch("pcie_test.sys.argv", ["pcie_test.py", "resource"])
    def test_main_resource_command(self, mock_list, mock_logger, mock_exit):
        """Test main with resource command"""
        mock_list.return_value = 0
        mock_logger.return_value = mock.Mock()
        main()
        self.assertEqual(mock_list.call_count, 1)
        mock_exit.assert_called_with(0)
        self.assertEqual(mock_exit.call_count, 1)

    @mock.patch("pcie_test.sys.exit")
    @mock.patch("pcie_test.init_logger")
    @mock.patch.object(PCIeTester, "check_link_state")
    @mock.patch(
        "pcie_test.sys.argv", ["pcie_test.py", "check_speed", "-s", "00:00.0"]
    )
    def test_main_check_speed_command(
        self, mock_check, mock_logger, mock_exit
    ):
        """Test main with check_speed command"""
        mock_check.return_value = 0
        mock_logger.return_value = mock.Mock()
        main()
        mock_check.assert_called_with("00:00.0", force=False)
        self.assertEqual(mock_check.call_count, 1)
        mock_exit.assert_called_with(0)
        self.assertEqual(mock_exit.call_count, 1)

    @mock.patch("pcie_test.sys.exit")
    @mock.patch("pcie_test.init_logger")
    @mock.patch.object(PCIeTester, "check_link_state")
    @mock.patch(
        "pcie_test.sys.argv",
        ["pcie_test.py", "check_speed", "-s", "00:00.0", "--force"],
    )
    def test_main_check_speed_with_force(
        self, mock_check, mock_logger, mock_exit
    ):
        """Test main with check_speed command and --force flag"""
        mock_check.return_value = 1
        mock_logger.return_value = mock.Mock()
        main()
        mock_check.assert_called_with("00:00.0", force=True)
        self.assertEqual(mock_check.call_count, 1)
        mock_exit.assert_called_with(1)
        self.assertEqual(mock_exit.call_count, 1)

    @mock.patch("pcie_test.sys.exit")
    @mock.patch("pcie_test.init_logger")
    @mock.patch.object(PCIeTester, "check_aspm_state")
    @mock.patch(
        "pcie_test.sys.argv", ["pcie_test.py", "check_aspm", "-s", "00:00.0"]
    )
    def test_main_check_aspm_command(self, mock_check, mock_logger, mock_exit):
        """Test main with check_aspm command"""
        mock_check.return_value = 0
        mock_logger.return_value = mock.Mock()
        main()
        mock_check.assert_called_with("00:00.0", force=False)
        self.assertEqual(mock_check.call_count, 1)
        mock_exit.assert_called_with(0)
        self.assertEqual(mock_exit.call_count, 1)

    @mock.patch("pcie_test.sys.exit")
    @mock.patch("pcie_test.init_logger")
    @mock.patch.object(PCIeTester, "check_aspm_state")
    @mock.patch(
        "pcie_test.sys.argv",
        ["pcie_test.py", "check_aspm", "-s", "00:00.0", "--force"],
    )
    def test_main_check_aspm_with_force(
        self, mock_check, mock_logger, mock_exit
    ):
        """Test main with check_aspm command and --force flag"""
        mock_check.return_value = 1
        mock_logger.return_value = mock.Mock()
        main()
        mock_check.assert_called_with("00:00.0", force=True)
        self.assertEqual(mock_check.call_count, 1)
        mock_exit.assert_called_with(1)
        self.assertEqual(mock_exit.call_count, 1)

    @mock.patch("pcie_test.sys.exit")
    @mock.patch("pcie_test.init_logger")
    @mock.patch.object(PCIeTester, "list_resources")
    @mock.patch("pcie_test.sys.argv", ["pcie_test.py", "--debug", "resource"])
    def test_main_with_debug_flag(self, mock_list, mock_logger, mock_exit):
        """Test main with --debug flag"""
        mock_list.return_value = 0
        mock_logger_instance = mock.Mock()
        mock_logger.return_value = mock_logger_instance
        main()
        mock_logger_instance.setLevel.assert_called_with(logging.DEBUG)
        self.assertEqual(mock_logger_instance.setLevel.call_count, 1)


if __name__ == "__main__":
    unittest.main()
