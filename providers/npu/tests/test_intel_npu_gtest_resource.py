#!/usr/bin/env python3
import unittest
import io
import subprocess
from collections import OrderedDict
from unittest.mock import patch, MagicMock

import intel_npu_gtest_resource

MOCK_GTEST_OUTPUT = """
Umd.File
ZeInitDriversTest.InitializeAndExecuteCopyCommand
MetricQuery.RunMetricQueryOnEmptyCommandList
ImmediateCmdList.FillCopyUsingBarriers
"""

MOCK_KNOWN_FAILURES = """
Device.GetZesEngineGetActivity
ExternalMemoryDmaHeap.DmaHeapToNpu/2KB
"""


class TestNpuResource(unittest.TestCase):

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_print_as_resource(self, mock_stdout):
        d = OrderedDict([("name", "Test1"), ("category", "CatA")])
        intel_npu_gtest_resource.print_as_resource(d)
        expected = "name: Test1\ncategory: CatA\n\n"
        self.assertEqual(mock_stdout.getvalue(), expected)

    def test_get_extra_flags(self):
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("ZeInitTest"),
            ["--ze-init-tests"],
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("NormalTest"), []
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("subprocess.run")
    @patch.dict("os.environ", {"NPU_UMD_TEST_CONFIG": "custom.yaml"})
    def test_main_logic(self, mock_run, mock_stdout):
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=MOCK_GTEST_OUTPUT
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=MOCK_KNOWN_FAILURES
            ),
        ]

        intel_npu_gtest_resource.main()

        self.assertEqual(mock_run.call_count, 2)

        first_call_args = mock_run.call_args_list[0][0][0]
        self.assertIn("custom.yaml", first_call_args)

        output = mock_stdout.getvalue()

        self.assertIn(
            "name: File\ncategory: Umd\nextra_flags: \ncert_status: blocker",
            output,
        )

        self.assertIn(
            "category: ZeInitDriversTest\nextra_flags: --ze-init-tests", output
        )

    @patch("subprocess.run")
    def test_subprocess_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("command not found")
        with self.assertRaises(FileNotFoundError):
            intel_npu_gtest_resource.main()


if __name__ == "__main__":
    unittest.main()
