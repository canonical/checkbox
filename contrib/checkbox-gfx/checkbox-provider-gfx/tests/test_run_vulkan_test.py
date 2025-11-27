#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock
import run_vulkan_cts

class MockProcess:
    """Simulates a running process for Popen."""
    def __init__(self, stdout_lines, stderr_output, return_code):
        # Simulate stdout as a file-like object that returns lines
        self.stdout = MagicMock()
        self.stdout.readline.side_effect = stdout_lines + ['']
        
        # Simulate stderr as a file-like object
        self.stderr = MagicMock()
        self.stderr.read.return_value = stderr_output
        
        # Define the return code
        self.return_code = return_code

    def wait(self):
        return self.return_code

class TestRunVulkanCTS(unittest.TestCase):

    @patch("run_vulkan_cts.sys.stdout.write")
    @patch("run_vulkan_cts.subprocess.Popen")
    @patch("run_vulkan_cts.exit")
    def test_run_vk_test_success(self, mock_exit, mock_run, mock_stdout):
        # Mock a successful subprocess result
        mock_output = [
            "Vulkan test passed line 1\n",
            "Vulkan test passed line 2\n",
        ]

        mock_result = MockProcess(
            stdout_lines=mock_output, 
            stderr_output="", 
            return_code=0
        )

        # mock_result.stdout = "Vulkan test passed"
        # mock_result.stderr = ""
        # mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_vulkan_cts.run_vk_test("foo/testlist.txt")

        mock_run.assert_called_once()
        mock_exit.assert_called_once_with(0)


    @patch("run_vulkan_cts.sys.stdout.write")
    @patch("run_vulkan_cts.subprocess.Popen")
    @patch("run_vulkan_cts.exit")
    def test_run_vk_test_failure(self, mock_exit, mock_run, mock_stdout):
        # Mock a successful subprocess result
        mock_output = [
            "Vulkan test passed line 1\n",
            "Vulkan test failed line 2\n",
        ]

        mock_result = MockProcess(
            stdout_lines=mock_output, 
            stderr_output="", 
            return_code=1
        )

        mock_run.return_value = mock_result

        run_vulkan_cts.run_vk_test("foo/testlist.txt")

        mock_run.assert_called_once()
        mock_exit.assert_called_once_with(1)


    # @patch("run_vulkan_cts.subprocess.run")
    # @patch("run_vulkan_cts.exit")
    # def test_run_vk_test_failure(self, mock_exit, mock_run):
    #     # Mock a failed subprocess result
    #     mock_result = MockProcess(
    #         stdout_lines=mock_output, 
    #         stderr_output="", 
    #         return_code=0
    #     )
    #     mock_result.stdout = ""
    #     mock_result.stderr = "error running Vulkan test (Expected)"
    #     mock_result.returncode = 1
    #     mock_run.return_value = mock_result

    #     run_vulkan_cts.run_vk_test("foo/testlist.txt")

    #     mock_run.assert_called_once()
    #     mock_exit.assert_called_once_with(1)
