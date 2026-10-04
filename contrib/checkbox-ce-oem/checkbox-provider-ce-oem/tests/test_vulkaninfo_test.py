#!/usr/bin/env python3

import io
import os
import subprocess
import unittest
from unittest.mock import patch

import vulkaninfo_test

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


class TestParsing(unittest.TestCase):
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
            [r["device_name"] for r in records],
            ["Intel(R) Graphics (LNL)", "llvmpipe (LLVM 21.1.8, 256 bits)"],
        )
        self.assertEqual(records[1]["device_type"], "PHYSICAL_DEVICE_TYPE_CPU")

    def test_parse_vulkaninfo_summary_returns_empty_without_devices(self):
        self.assertEqual(
            vulkaninfo_test.parse_vulkaninfo_summary("no devices here\n"),
            [],
        )

    def test_iter_gpu_blocks_splits_by_device(self):
        blocks = vulkaninfo_test._iter_gpu_blocks(
            SUMMARY_OUTPUT_HW_AND_SW_DEVICES
        )

        self.assertEqual([number for number, _ in blocks], ["0", "1"])
        self.assertIn(
            "\tdeviceName         = Intel(R) Graphics (LNL)",
            blocks[0][1],
        )
        self.assertNotIn(
            "\tdriverName         = llvmpipe",
            blocks[0][1],
        )

    def test_build_record_defaults_missing_fields_to_empty_string(self):
        record = vulkaninfo_test._build_record("0", ["not a field line"])

        self.assertEqual(
            record,
            {"device_number": "0", "device_name": "", "device_type": ""},
        )


class TestVulkaninfoEnviron(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"LD_LIBRARY_PATH": "/snap/checkbox24/current/usr/lib", "A": "1"},
        clear=True,
    )
    def test_drops_inherited_ld_library_path(self):
        self.assertEqual(vulkaninfo_test.vulkaninfo_environ(), {"A": "1"})

    @patch.dict(
        os.environ,
        {
            "LD_LIBRARY_PATH": "/snap/checkbox24/current/usr/lib",
            "VULKANINFO_LD_LIBRARY_PATH": "/opt/gpu/lib",
        },
        clear=True,
    )
    def test_uses_vulkaninfo_ld_library_path(self):
        env = vulkaninfo_test.vulkaninfo_environ()

        self.assertEqual(env["LD_LIBRARY_PATH"], "/opt/gpu/lib")


@patch.dict(os.environ, {}, clear=True)
@patch("vulkaninfo_test.subprocess.check_output")
class TestRunVulkaninfoSummary(unittest.TestCase):
    def test_default_command(self, mock_check_output):
        mock_check_output.return_value = "out"

        self.assertEqual(vulkaninfo_test.run_vulkaninfo_summary(), "out")
        self.assertEqual(
            mock_check_output.call_args[0][0], ["vulkaninfo", "--summary"]
        )
        self.assertNotIn(
            "LD_LIBRARY_PATH", mock_check_output.call_args[1]["env"]
        )

    def test_custom_command_from_environ(self, mock_check_output):
        os.environ["CUSTOM_VULKAN_COMMAND_PATH"] = "snap.vulkaninfo"
        os.environ["VK_ICD_FILENAMES"] = "/icd.json"

        vulkaninfo_test.run_vulkaninfo_summary()

        self.assertEqual(
            mock_check_output.call_args[0][0],
            ["snap.vulkaninfo", "--summary"],
        )

    def test_command_not_found(self, mock_check_output):
        mock_check_output.side_effect = FileNotFoundError("vulkaninfo")

        with self.assertRaises(SystemExit):
            vulkaninfo_test.run_vulkaninfo_summary()

    def test_crash(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(
            -11, ["vulkaninfo", "--summary"], output="partial"
        )

        with self.assertRaises(SystemExit):
            vulkaninfo_test.run_vulkaninfo_summary()


@patch("vulkaninfo_test.run_vulkaninfo_summary")
class TestCmdResource(unittest.TestCase):
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_only_emits_hardware_devices(self, mock_stdout, mock_run):
        mock_run.return_value = SUMMARY_OUTPUT_HW_AND_SW_DEVICES

        self.assertEqual(vulkaninfo_test.cmd_resource(), 0)

        output = mock_stdout.getvalue()
        self.assertIn("device_number: 0", output)
        self.assertIn("device_name: Intel(R) Graphics (LNL)", output)
        self.assertNotIn("llvmpipe", output)

    def test_fails_when_no_hardware_device_found(self, mock_run):
        mock_run.return_value = (
            "GPU0:\n"
            "\tdeviceType         = PHYSICAL_DEVICE_TYPE_CPU\n"
            "\tdeviceName         = llvmpipe\n"
        )

        with self.assertRaises(SystemExit):
            vulkaninfo_test.cmd_resource()


@patch("vulkaninfo_test.run_vulkaninfo_summary")
class TestCmdTest(unittest.TestCase):
    def test_fails_on_empty_output(self, mock_run):
        mock_run.return_value = ""

        with self.assertRaises(SystemExit):
            vulkaninfo_test.cmd_test()

    def test_fails_on_software_renderer_unscoped(self, mock_run):
        mock_run.return_value = SUMMARY_OUTPUT_HW_AND_SW_DEVICES

        with self.assertRaises(SystemExit):
            vulkaninfo_test.cmd_test()

    def test_passes_for_hw_device_despite_sw_device_present(self, mock_run):
        mock_run.return_value = SUMMARY_OUTPUT_HW_AND_SW_DEVICES

        self.assertEqual(vulkaninfo_test.cmd_test(device_number="0"), 0)

    def test_fails_for_sw_device_when_scoped(self, mock_run):
        mock_run.return_value = SUMMARY_OUTPUT_HW_AND_SW_DEVICES

        with self.assertRaises(SystemExit):
            vulkaninfo_test.cmd_test(device_number="1")

    def test_fails_when_requested_device_number_missing(self, mock_run):
        mock_run.return_value = SUMMARY_OUTPUT_SINGLE_HW_DEVICE

        with self.assertRaises(SystemExit):
            vulkaninfo_test.cmd_test(device_number="9")

    def test_passes_with_clean_hardware_output(self, mock_run):
        mock_run.return_value = SUMMARY_OUTPUT_SINGLE_HW_DEVICE

        result = vulkaninfo_test.cmd_test(
            device_number="0", device_name="Mali-G720-Immortalis"
        )

        self.assertEqual(result, 0)


class TestMain(unittest.TestCase):
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
