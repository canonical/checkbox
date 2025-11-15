#!/usr/bin/env python3
import unittest
import io
import sys
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import intel_npu_gtest_resource


class TestHelperFunctions(unittest.TestCase):

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_print_as_resource(self, mock_stdout):
        """Test that the dictionary is printed in the correct format."""
        d = {"name": "Test1", "category": "CatA", "value": 123}
        intel_npu_gtest_resource.print_as_resource(d)

        expected_output = "name: Test1\n" "category: CatA\n" "value: 123\n\n"
        self.assertEqual(mock_stdout.getvalue(), expected_output)

    def test_get_extra_flags(self):
        # ZeInit tests
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("ZeInitDriversTest"),
            ["--ze-init-tests"],
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("ZeInitTest"),
            ["--ze-init-tests"],
        )
        # Check that other tests don't get extra flags
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("Command"), []
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("Metric"), []
        )

    def test_get_metric_streamer_allowed_states(self):
        # Categories that need metric streamer support
        self.assertEqual(
            intel_npu_gtest_resource.get_metric_streamer_allowed_states(
                "MetricQuery"
            ),
            ["supported"],
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_metric_streamer_allowed_states(
                "MetricQueryPool"
            ),
            ["supported"],
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_metric_streamer_allowed_states(
                "Metric"
            ),
            ["supported"],
        )

        # Other category names that shouldn't require metric streamer support
        self.assertEqual(
            intel_npu_gtest_resource.get_metric_streamer_allowed_states(
                "Command"
            ),
            ["supported", "unsupported"],
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_metric_streamer_allowed_states(
                "ZeInitTest"
            ),
            ["supported", "unsupported"],
        )

    def test_get_ivpu_bo_create_allowed_states(self):
        self.assertEqual(
            intel_npu_gtest_resource.get_ivpu_bo_create_allowed_states(
                "CompilerInDriverWithProfiling", "TestName"
            ),
            ["supported"],
        )

        self.assertEqual(
            intel_npu_gtest_resource.get_ivpu_bo_create_allowed_states(
                "CommandMemoryFill", "TestName"
            ),
            ["supported"],
        )

        self.assertEqual(
            intel_npu_gtest_resource.get_ivpu_bo_create_allowed_states(
                "ImmediateCmdList", "FillCopyUsingBarriers"
            ),
            ["supported"],
        )

        self.assertEqual(
            intel_npu_gtest_resource.get_ivpu_bo_create_allowed_states(
                "ImmediateCmdList", "SomeOtherTest"
            ),
            ["supported", "unsupported"],
        )

        self.assertEqual(
            intel_npu_gtest_resource.get_ivpu_bo_create_allowed_states(
                "SomeCategory", "FillCopyUsingBarriers"
            ),
            ["supported", "unsupported"],
        )

        self.assertEqual(
            intel_npu_gtest_resource.get_ivpu_bo_create_allowed_states(
                "Umd", "File"
            ),
            ["supported", "unsupported"],
        )

    def test_is_known_failure(self):
        self.assertTrue(
            intel_npu_gtest_resource.is_known_failure(
                "ExternalMemoryZe", "GpuZeFillToNpuZeCopy"
            )
        )

        self.assertTrue(
            intel_npu_gtest_resource.is_known_failure(
                "ExternalMemoryDmaHeap", "DmaHeapToNpu/2KB"
            )
        )

        self.assertTrue(
            intel_npu_gtest_resource.is_known_failure(
                "Device", "GetZesEngineGetActivity"
            )
        )

        self.assertTrue(
            intel_npu_gtest_resource.is_known_failure(
                "DriverCache", "CheckWhenSpaceLessThanAllBlobs"
            )
        )

        self.assertTrue(
            intel_npu_gtest_resource.is_known_failure(
                "CommandQueuePriority",
                "executeManyLowPriorityJobsExpectHighPriorityJobCompletesFirst",
            )
        )

        self.assertFalse(
            intel_npu_gtest_resource.is_known_failure("Umd", "File")
        )

        self.assertFalse(
            intel_npu_gtest_resource.is_known_failure(
                "Command", "CreateCloseAndDestroyList"
            )
        )


MOCK_GTEST_OUTPUT = """
Umd.File
ZeInitDriversTest.InitializeAndExecuteCopyCommand
MetricQuery.RunMetricQueryOnEmptyCommandList
Device.GetZesEngineGetActivity
ExternalMemoryDmaHeap.DmaHeapToNpu/2KB
ImmediateCmdList.FillCopyUsingBarriers
ImmediateCmdList.MetricQueryTest
CommandQueuePriority.executeManyLowPriorityJobsExpectHighPriorityJobCompletesFirst
CommandMemoryFill.FillMemoryWithPattern/0
"""


class TestMainFunction(unittest.TestCase):
    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("subprocess.run")
    @patch.dict(
        "os.environ",
        {
            "NPU_UMD_TEST_CONFIG": "/fake/home/snap/intel-npu-driver/current/basic.yaml"
        },
    )
    def test_main_logic_with_filtering(self, mock_run, mock_stdout):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=MOCK_GTEST_OUTPUT
        )

        return_code = intel_npu_gtest_resource.main()
        self.assertIsNone(return_code)

        expected_config_path = Path(
            "/fake/home/snap/intel-npu-driver/current/basic.yaml"
        )
        mock_run.assert_called_once_with(
            [
                "intel-npu-driver.npu-umd-test",
                "-l",
                "--config",
                expected_config_path,
            ],
            capture_output=True,
            text=True,
        )

        output = mock_stdout.getvalue()

        self.assertIn(
            "name: File\n"
            "category: Umd\n"
            "extra_flags: \n"
            "metric_streamer_allowed_states: ['supported', 'unsupported']\n"
            "ivpu_bo_create_allowed_states: ['supported', 'unsupported']\n",
            output,
        )

        self.assertIn(
            "name: InitializeAndExecuteCopyCommand\n"
            "category: ZeInitDriversTest\n"
            "extra_flags: --ze-init-tests\n"
            "metric_streamer_allowed_states: ['supported', 'unsupported']\n"
            "ivpu_bo_create_allowed_states: ['supported', 'unsupported']\n",
            output,
        )

        self.assertIn(
            "name: RunMetricQueryOnEmptyCommandList\n"
            "category: MetricQuery\n"
            "extra_flags: \n"
            "metric_streamer_allowed_states: ['supported']\n"
            "ivpu_bo_create_allowed_states: ['supported', 'unsupported']\n",
            output,
        )

        self.assertIn(
            "name: FillCopyUsingBarriers\n"
            "category: ImmediateCmdList\n"
            "extra_flags: \n"
            "metric_streamer_allowed_states: ['supported', 'unsupported']\n"
            "ivpu_bo_create_allowed_states: ['supported']\n",
            output,
        )

        self.assertIn(
            "name: MetricQueryTest\n"
            "category: ImmediateCmdList\n"
            "extra_flags: \n"
            "metric_streamer_allowed_states: ['supported', 'unsupported']\n"
            "ivpu_bo_create_allowed_states: ['supported', 'unsupported']\n",
            output,
        )

        self.assertIn(
            "name: FillMemoryWithPattern/0\n"
            "category: CommandMemoryFill\n"
            "extra_flags: \n"
            "metric_streamer_allowed_states: ['supported', 'unsupported']\n"
            "ivpu_bo_create_allowed_states: ['supported']\n",
            output,
        )

        # Check that known failures don't end up in the resource
        self.assertNotIn("name: GetZesEngineGetActivity", output)
        self.assertNotIn("name: DmaHeapToNpu/2KB", output)
        self.assertNotIn(
            "name: executeManyLowPriorityJobsExpectHighPriorityJobCompletesFirst",
            output,
        )

    @patch("subprocess.run")
    @patch.dict(
        "os.environ",
        {
            "NPU_UMD_TEST_CONFIG": "/fake/home/snap/intel-npu-driver/current/basic.yaml"
        },
    )
    def test_main_subprocess_not_found(self, mock_run):
        # Check that the script will raise an exception if the script doesn't exist
        mock_run.side_effect = FileNotFoundError("command not found")

        with self.assertRaises(FileNotFoundError):
            intel_npu_gtest_resource.main()


if __name__ == "__main__":
    unittest.main()
