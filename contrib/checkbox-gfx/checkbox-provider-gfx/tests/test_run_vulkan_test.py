#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock
import run_vulkan_cts


class TestRunVulkanCTS(unittest.TestCase):

    @patch("run_vulkan_cts.subprocess.run")
    @patch("run_vulkan_cts.exit")
    def test_run_vk_test_success(self, mock_exit, mock_run):
        # Mock a successful subprocess result
        mock_result = MagicMock()
        mock_result.stdout = "test passed"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_vulkan_cts.run_vk_test("foo/testlist.txt")

        mock_run.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("run_vulkan_cts.subprocess.run")
    @patch("run_vulkan_cts.exit")
    def test_run_vk_test_failure(self, mock_exit, mock_run):
        # Mock a failed subprocess result
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "error running test"
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        run_vulkan_cts.run_vk_test("foo/testlist.txt")

        mock_run.assert_called_once()
        mock_exit.assert_called_once_with(1)
