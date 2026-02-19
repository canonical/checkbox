#!/usr/bin/env python3
import unittest
import io
import subprocess
from unittest.mock import patch, MagicMock
from collections import OrderedDict

import intel_npu_gtest_resource

FULL_GTEST_LIST = """
Umd.ZeDevTypeStr
Device.GetZesEngineGetActivity
ExternalMemoryZe.GpuZeFillToNpuZeCopy
ExternalMemoryDmaHeap.DmaHeapToNpu/2KB
ExternalMemoryDmaHeap.DmaHeapToNpu/16MB
ZeInitDriversTest.InitializeAndExecuteCopyCommand
CommandMemoryFill.FillMemoryWithPattern/0
"""

KNOWN_FAILURES_LIST = """
Device.GetZesEngineGetActivity
ExternalMemoryZe.GpuZeFillToNpuZeCopy
ExternalMemoryDmaHeap.DmaHeapToNpu/2KB
ExternalMemoryDmaHeap.DmaHeapToNpu/16MB
"""

class TestIntelNpuGtestResource(unittest.TestCase):
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_print_as_resource_formatting(self, mock_stdout):
        test_data = OrderedDict([("key1", "val1"), ("key2", True)])
        intel_npu_gtest_resource.print_as_resource(test_data)

        expected_output = "key1: val1\nkey2: True\n\n"
        self.assertEqual(mock_stdout.getvalue(), expected_output)

    @patch('subprocess.check_output')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_parsing_logic(self, mock_stdout, mock_subproc):

        mock_subproc.side_effect = [
            "Category.TestWith.Multiple.Dots\n" +
            "DmaHeapCategory.DmaHeapToNpu/4MB\n" +
            "BadLineNoDot\n",

            "Category.TestWith.Multiple.Dots\n"
        ]

        with patch('argparse.ArgumentParser.parse_args', return_value=MagicMock()):
            intel_npu_gtest_resource.main()

        output = mock_stdout.getvalue()

        self.assertIn("name: TestWith.Multiple.Dots", output)
        self.assertIn("category: Category", output)
        self.assertIn("known_failure: True", output)

        self.assertIn("name: DmaHeapToNpu/4MB", output)
        self.assertIn("extra_flags: --dma-heap", output)
        self.assertIn("known_failure: False", output)

        self.assertNotIn("name: BadLineNoDot", output)

    @patch('subprocess.check_output')
    @patch('os.environ.get')
    def test_main_config_selection(self, mock_env, mock_subproc):
        mock_subproc.return_value = "Cat.Test\n"

        mock_env.return_value = "custom.yaml"
        with patch('sys.stdout', new_callable=io.StringIO):
            with patch('argparse.ArgumentParser.parse_args', return_value=MagicMock()):
                intel_npu_gtest_resource.main()
        self.assertIn("custom.yaml", mock_subproc.call_args_list[0][0][0])

        mock_env.return_value = None
        with patch('sys.stdout', new_callable=io.StringIO):
            with patch('argparse.ArgumentParser.parse_args', return_value=MagicMock()):
                intel_npu_gtest_resource.main()
        self.assertIn("basic.yaml", mock_subproc.call_args_list[2][0][0])


    @patch('subprocess.check_output')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_known_failures_identification(self, mock_stdout, mock_subprocess):
        mock_subprocess.side_effect = [
            FULL_GTEST_LIST,
            KNOWN_FAILURES_LIST
        ]

        with patch('argparse.ArgumentParser.parse_args', return_value=MagicMock()):
            intel_npu_gtest_resource.main()

        output = mock_stdout.getvalue()

        self.assertIn("name: GetZesEngineGetActivity\ncategory: Device\nextra_flags: \nknown_failure: True", output)
        self.assertIn("name: InitializeAndExecuteCopyCommand\ncategory: ZeInitDriversTest\nextra_flags: --ze-init-tests\nknown_failure: False", output)
        self.assertIn("name: DmaHeapToNpu/2KB\ncategory: ExternalMemoryDmaHeap\nextra_flags: --dma-heap\nknown_failure: True", output)
        self.assertIn("name: DmaHeapToNpu/16MB\ncategory: ExternalMemoryDmaHeap\nextra_flags: --dma-heap\nknown_failure: True", output)
        self.assertIn("name: ZeDevTypeStr\ncategory: Umd\nextra_flags: \nknown_failure: False", output)

    def test_extra_flags_logic_extended(self):
        self.assertEqual(intel_npu_gtest_resource.get_extra_flags("ZeInitTest"), ["--ze-init-tests"])
        self.assertEqual(intel_npu_gtest_resource.get_extra_flags("ExternalMemoryDmaHeap"), ["--dma-heap"])
        self.assertEqual(intel_npu_gtest_resource.get_extra_flags("ZeInitDmaHeapCategory"), ["--ze-init-tests", "--dma-heap"])

    @patch('subprocess.check_output')
    def test_empty_failure_list(self, mock_subprocess):
        mock_subprocess.side_effect = ["Umd.Test\n", ""] 

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with patch('argparse.ArgumentParser.parse_args', return_value=MagicMock()):
                intel_npu_gtest_resource.main()

            self.assertIn("known_failure: False", mock_stdout.getvalue())

if __name__ == "__main__":
    unittest.main()
