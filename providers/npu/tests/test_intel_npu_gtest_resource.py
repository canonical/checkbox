#!/usr/bin/env python3
import unittest
import io
import subprocess
from unittest.mock import patch
import intel_npu_gtest_resource

# More comprehensive mock data
MOCK_GTEST_OUTPUT = """
Umd.File
ZeInitDriversTest.InitializeAndExecuteCopyCommand
MetricQuery.RunMetricQueryOnEmptyCommandList
Device.GetZesEngineGetActivity
ExternalMemoryDmaHeap.DmaHeapToNpu/2KB
ImmediateCmdList.FillCopyUsingBarriers
CommandMemoryFill.FillMemoryWithPattern/0
MalformedLineWithoutDot
"""

MOCK_FAILURES_OUTPUT = """
Device.GetZesEngineGetActivity
ExternalMemoryDmaHeap.DmaHeapToNpu/2KB
"""


class TestFiltering(unittest.TestCase):

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("subprocess.run")
    @patch("sys.argv", ["script.py", "--mode", "blocker"])
    def test_expanded_blockers(self, mock_run, mock_stdout):
        """Verify that multiple clean tests pass and known failures are excluded."""
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=MOCK_GTEST_OUTPUT
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=MOCK_FAILURES_OUTPUT
            ),
        ]
        intel_npu_gtest_resource.main()
        output = mock_stdout.getvalue()

        # Should be present (Clean tests)
        self.assertIn("name: File\ncategory: Umd", output)
        self.assertIn(
            "name: FillCopyUsingBarriers\ncategory: ImmediateCmdList", output
        )
        self.assertIn("name: FillMemoryWithPattern/0", output)

        # Should be absent (These are in the failures list)
        self.assertNotIn("name: GetZesEngineGetActivity", output)
        self.assertNotIn("name: DmaHeapToNpu/2KB", output)

        # Should handle ZeInit flags correctly in the output
        self.assertIn(
            "category: ZeInitDriversTest\nextra_flags: --ze-init-tests", output
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("subprocess.run")
    @patch("sys.argv", ["script.py", "--mode", "non-blocker"])
    def test_expanded_non_blockers(self, mock_run, mock_stdout):
        """Verify that only the known failures are printed."""
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=MOCK_GTEST_OUTPUT
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=MOCK_FAILURES_OUTPUT
            ),
        ]
        intel_npu_gtest_resource.main()
        output = mock_stdout.getvalue()

        # Should be present (These are the known failures)
        self.assertIn(
            "name: GetZesEngineGetActivity\ncategory: Device", output
        )
        self.assertIn(
            "name: DmaHeapToNpu/2KB\ncategory: ExternalMemoryDmaHeap", output
        )

        # Should be absent (These are clean/passing tests)
        self.assertNotIn("name: File\ncategory: Umd", output)
        self.assertNotIn("name: FillMemoryWithPattern/0", output)

    def test_get_extra_flags_edge_cases(self):
        """Check various category prefixes for flag assignment."""
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("ZeInit"),
            ["--ze-init-tests"],
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("ZeInitSomething"),
            ["--ze-init-tests"],
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("zeinit"), []
        )
        self.assertEqual(
            intel_npu_gtest_resource.get_extra_flags("Compute"), []
        )


if __name__ == "__main__":
    unittest.main()
