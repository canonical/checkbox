#!/usr/bin/env python3

import io
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPT_DIR = os.path.dirname(__file__)
BIN_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "bin"))
CHECKBOX_SUPPORT_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "..", "..", "..", "checkbox-support")
)
CHECKBOX_NG_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "..", "..", "..", "checkbox-ng")
)
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)
if CHECKBOX_SUPPORT_DIR not in sys.path:
    sys.path.insert(0, CHECKBOX_SUPPORT_DIR)
if CHECKBOX_NG_DIR not in sys.path:
    sys.path.insert(0, CHECKBOX_NG_DIR)

import vulkaninfo_test


def _completed_process(returncode, stdout):
    return subprocess.CompletedProcess(
        args="vulkaninfo --summary",
        returncode=returncode,
        stdout=stdout,
    )


SUMMARY_OUTPUT_SINGLE_HW_DEVICE = (
    "Devices:\n"
    "========\n"
    "GPU0:\n"
    "\tapiVersion         = 1.4.305\n"
    "\tdriverVersion      = 54.1.0\n"
    "\tvendorID           = 0x13b5\n"
    "\tdeviceID           = 0xc8700000\n"
    "\tdeviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
    "\tdeviceName         = Mali-G720-Immortalis\n"
    "\tdriverID           = DRIVER_ID_ARM_PROPRIETARY\n"
)

SUMMARY_OUTPUT_HW_AND_SW_DEVICES = (
    "Devices:\n"
    "========\n"
    "GPU0:\n"
    "\tapiVersion         = 1.4.335\n"
    "\tdeviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
    "\tdeviceName         = Intel(R) Graphics (LNL)\n"
    "\tdriverName         = Intel open-source Mesa driver\n"
    "GPU1:\n"
    "\tapiVersion         = 1.4.335\n"
    "\tdeviceType         = PHYSICAL_DEVICE_TYPE_CPU\n"
    "\tdeviceName         = llvmpipe (LLVM 21.1.8, 256 bits)\n"
    "\tdriverName         = llvmpipe\n"
)


class TestVulkaninfoTest(unittest.TestCase):
    @patch(
        "vulkaninfo_test.resolve_configured_commands",
        return_value={"vulkaninfo": "cmd"},
    )
    def test_resolve_vulkaninfo_command_delegates_to_general_utils(
        self,
        mock_resolve,
    ):
        result = vulkaninfo_test._resolve_vulkaninfo_command(
            enable_logger=False
        )

        self.assertEqual(result, "cmd")
        mock_resolve.assert_called_once_with(
            default_commands=[vulkaninfo_test.EXECUTABLE_CMD],
            enable_logger=False,
        )

    def test_parse_vulkaninfo_summary_single_device(self):
        records = vulkaninfo_test.parse_vulkaninfo_summary(
            SUMMARY_OUTPUT_SINGLE_HW_DEVICE
        )

        self.assertEqual(
            records,
            [
                {
                    "device_number": "0",
                    "device_name": "Mali-G720-Immortalis",
                    "device_type": "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
                }
            ],
        )

    def test_parse_vulkaninfo_summary_multiple_devices(self):
        records = vulkaninfo_test.parse_vulkaninfo_summary(
            SUMMARY_OUTPUT_HW_AND_SW_DEVICES
        )

        self.assertEqual(
            records,
            [
                {
                    "device_number": "0",
                    "device_name": "Intel(R) Graphics (LNL)",
                    "device_type": "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
                },
                {
                    "device_number": "1",
                    "device_name": "llvmpipe (LLVM 21.1.8, 256 bits)",
                    "device_type": "PHYSICAL_DEVICE_TYPE_CPU",
                },
            ],
        )

    def test_parse_vulkaninfo_summary_returns_empty_without_devices(self):
        self.assertEqual(
            vulkaninfo_test.parse_vulkaninfo_summary("no devices here\n"),
            [],
        )

    def test_extract_device_block_returns_matching_block_only(self):
        block = vulkaninfo_test.extract_device_block(
            SUMMARY_OUTPUT_HW_AND_SW_DEVICES, "1"
        )

        self.assertIn("GPU1:", block)
        self.assertIn("llvmpipe", block)
        self.assertNotIn("Intel(R) Graphics", block)

    def test_extract_device_block_returns_empty_when_not_found(self):
        block = vulkaninfo_test.extract_device_block(
            SUMMARY_OUTPUT_SINGLE_HW_DEVICE, "9"
        )

        self.assertEqual(block, "")

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_cmd_resource_only_emits_hardware_devices(
        self,
        mock_stdout,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            0, SUMMARY_OUTPUT_HW_AND_SW_DEVICES
        )

        result = vulkaninfo_test.cmd_resource()

        output = mock_stdout.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("device_number: 0", output)
        self.assertIn("device_name: Intel(R) Graphics (LNL)", output)
        self.assertNotIn("llvmpipe", output)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_resource_returns_1_when_no_hardware_device_found(
        self,
        mock_run,
        _mock_resolve,
    ):
        software_only_output = (
            "Devices:\n"
            "========\n"
            "GPU0:\n"
            "\tdeviceType         = PHYSICAL_DEVICE_TYPE_CPU\n"
            "\tdeviceName         = llvmpipe\n"
        )
        mock_run.return_value = _completed_process(0, software_only_output)

        self.assertEqual(vulkaninfo_test.cmd_resource(), 1)

    @patch("vulkaninfo_test._resolve_vulkaninfo_command", return_value="")
    def test_cmd_resource_fails_when_command_not_found(self, _mock_resolve):
        self.assertEqual(vulkaninfo_test.cmd_resource(), 1)

    @patch("vulkaninfo_test._resolve_vulkaninfo_command", return_value="")
    def test_cmd_test_fails_when_command_not_found(self, _mock_resolve):
        self.assertEqual(vulkaninfo_test.cmd_test(), 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_fails_on_empty_output(self, mock_run, _mock_resolve):
        mock_run.return_value = _completed_process(0, "")

        self.assertEqual(vulkaninfo_test.cmd_test(), 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_fails_on_crash_text(self, mock_run, _mock_resolve):
        mock_run.return_value = _completed_process(
            139, "Segmentation fault (core dumped)\n"
        )

        self.assertEqual(vulkaninfo_test.cmd_test(), 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_fails_on_nonzero_returncode_without_crash_text(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            139, "some unexpected output\n"
        )

        self.assertEqual(vulkaninfo_test.cmd_test(), 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_fails_on_small_nonzero_returncode(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            1, SUMMARY_OUTPUT_SINGLE_HW_DEVICE
        )

        self.assertEqual(vulkaninfo_test.cmd_test(), 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_fails_on_software_renderer_unscoped(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            0, SUMMARY_OUTPUT_HW_AND_SW_DEVICES
        )

        self.assertEqual(vulkaninfo_test.cmd_test(), 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_passes_for_hw_device_despite_sw_device_present(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            0, SUMMARY_OUTPUT_HW_AND_SW_DEVICES
        )

        result = vulkaninfo_test.cmd_test(device_number="0")

        self.assertEqual(result, 0)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_fails_for_sw_device_when_scoped(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            0, SUMMARY_OUTPUT_HW_AND_SW_DEVICES
        )

        result = vulkaninfo_test.cmd_test(device_number="1")

        self.assertEqual(result, 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_fails_when_requested_device_number_missing(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            0, SUMMARY_OUTPUT_SINGLE_HW_DEVICE
        )

        result = vulkaninfo_test.cmd_test(device_number="9")

        self.assertEqual(result, 1)

    @patch(
        "vulkaninfo_test._resolve_vulkaninfo_command",
        return_value="vulkaninfo",
    )
    @patch("vulkaninfo_test.subprocess.run")
    def test_cmd_test_passes_with_clean_hardware_output(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = _completed_process(
            0, SUMMARY_OUTPUT_SINGLE_HW_DEVICE
        )

        result = vulkaninfo_test.cmd_test(
            device_number="0", device_name="Mali-G720-Immortalis"
        )

        self.assertEqual(result, 0)

    @patch("vulkaninfo_test.cmd_resource", return_value=8)
    @patch("sys.argv", ["vulkaninfo_test.py", "resource"])
    def test_main_routes_resource(self, mock_cmd_resource):
        self.assertEqual(vulkaninfo_test.main(), 8)
        mock_cmd_resource.assert_called_once_with()

    @patch("vulkaninfo_test.cmd_test", return_value=9)
    @patch(
        "sys.argv",
        ["vulkaninfo_test.py", "test", "-dn", "0", "-n", "device"],
    )
    def test_main_routes_test(self, mock_cmd_test):
        self.assertEqual(vulkaninfo_test.main(), 9)
        mock_cmd_test.assert_called_once_with("0", "device")

    @patch("vulkaninfo_test.logger")
    @patch("sys.argv", ["vulkaninfo_test.py", "test", "--debug"])
    @patch("vulkaninfo_test.cmd_test", return_value=0)
    def test_main_debug_enables_debug_logging(
        self,
        _mock_cmd_test,
        mock_logger,
    ):
        self.assertEqual(vulkaninfo_test.main(), 0)
        mock_logger.setLevel.assert_called_once_with(
            vulkaninfo_test.logging.DEBUG
        )


if __name__ == "__main__":
    unittest.main()
