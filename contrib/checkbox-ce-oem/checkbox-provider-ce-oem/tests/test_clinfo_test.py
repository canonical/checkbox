#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import clinfo_test


class TestClinfoTest(unittest.TestCase):
    @patch("clinfo_test.shutil.which", return_value=None)
    def test_resolve_binary_raises_when_missing(self, _mock_which):
        with self.assertRaises(FileNotFoundError):
            clinfo_test.resolve_binary("clinfo")

    @patch("clinfo_test.resolve_binary", return_value="/usr/bin/clinfo")
    @patch("clinfo_test.run_clinfo")
    @patch("clinfo_test.logger")
    def test_cmd_test_pass_with_default_validation_set(
        self, mock_logger, mock_run_clinfo, _mock_resolve_binary
    ):
        prop_values = {
            "CL_DEVICE_AVAILABLE": "CL_TRUE",
            "CL_DEVICE_COMPILER_AVAILABLE": "CL_TRUE",
            "CL_DEVICE_EXECUTION_CAPABILITIES": "CL_EXEC_KERNEL",
        }

        def side_effect(_binary_path, args, capture_output=False):
            self.assertTrue(capture_output)
            prop_name = args[3]
            output = "[ARM/0]    {}    {}\n".format(
                prop_name,
                prop_values[prop_name],
            )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=output,
                stderr="",
            )

        mock_run_clinfo.side_effect = side_effect

        result = clinfo_test.cmd_test(
            binary="clinfo",
            validation_json_path="",
            platform="ARM Platform",
            platform_number=0,
            device="Mali-G57 r0p1",
            device_number=0,
        )

        self.assertEqual(result, 0)
        self.assertEqual(mock_run_clinfo.call_count, 3)
        mock_logger.info.assert_any_call("Validated OpenCL properties:")
        for prop_name, prop_value in prop_values.items():
            mock_logger.info.assert_any_call(
                "%s", "{}: {}".format(prop_name, prop_value)
            )

    @patch("clinfo_test.resolve_binary", return_value="/usr/bin/clinfo")
    @patch("clinfo_test.run_clinfo")
    def test_cmd_test_pass_with_custom_validation_file(
        self, mock_run_clinfo, _mock_resolve_binary
    ):
        payload = {
            "NVIDIA CUDA": {
                "NVIDIA RTX A4000": {
                    "CL_DEVICE_MAX_COMPUTE_UNITS": 4,
                    "CL_DEVICE_LINKER_AVAILABLE": "CL_TRUE",
                }
            }
        }

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, encoding="utf-8"
        ) as file_obj:
            json.dump(payload, file_obj)
            validation_path = file_obj.name

        self.addCleanup(os.unlink, validation_path)

        def side_effect(_binary_path, args, capture_output=False):
            self.assertTrue(capture_output)
            prop_name = args[3]
            prop_values = {
                "CL_DEVICE_MAX_COMPUTE_UNITS": "4",
                "CL_DEVICE_LINKER_AVAILABLE": "CL_TRUE",
            }
            output = "[NVIDIA/0]    {}    {}\n".format(
                prop_name,
                prop_values[prop_name],
            )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=output,
                stderr="",
            )

        mock_run_clinfo.side_effect = side_effect

        result = clinfo_test.cmd_test(
            binary="clinfo",
            validation_json_path=validation_path,
            platform="NVIDIA CUDA",
            platform_number=1,
            device="NVIDIA RTX A4000",
            device_number=0,
        )

        self.assertEqual(result, 0)
        self.assertEqual(mock_run_clinfo.call_count, 2)

    @patch("clinfo_test.resolve_binary", return_value="/usr/bin/clinfo")
    @patch("clinfo_test.run_clinfo")
    def test_cmd_test_fail_when_value_mismatch(
        self, mock_run_clinfo, _mock_resolve_binary
    ):
        def side_effect(_binary_path, args, capture_output=False):
            self.assertTrue(capture_output)
            prop_name = args[3]
            value = "CL_FALSE" if prop_name == "CL_DEVICE_AVAILABLE" else "CL_TRUE"
            if prop_name == "CL_DEVICE_EXECUTION_CAPABILITIES":
                value = "CL_EXEC_KERNEL"
            output = "[ARM/0]    {}    {}\n".format(prop_name, value)
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=output,
                stderr="",
            )

        mock_run_clinfo.side_effect = side_effect

        result = clinfo_test.cmd_test(
            binary="clinfo",
            validation_json_path="",
            platform="ARM Platform",
            platform_number=0,
            device="Mali-G57 r0p1",
            device_number=0,
        )

        self.assertEqual(result, 1)

    def test_load_validation_set_missing_file(self):
        result = clinfo_test.load_validation_set(
            validation_json_path="/tmp/no-such-file.json",
            platform="ARM Platform",
            device="Mali-G57 r0p1",
        )

        self.assertIsNone(result)

    def test_parse_property_value(self):
        output = (
            "[ARM/0]    CL_DEVICE_AVAILABLE                             "
            "CL_TRUE\n"
        )
        self.assertEqual(
            clinfo_test.parse_property_value(output, "CL_DEVICE_AVAILABLE"),
            "CL_TRUE",
        )


if __name__ == "__main__":
    unittest.main()
