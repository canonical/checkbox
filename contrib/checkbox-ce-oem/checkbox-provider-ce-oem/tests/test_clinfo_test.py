#!/usr/bin/env python3

import io
import os
import subprocess
import sys
import unittest
from unittest.mock import patch


SCRIPT_DIR = os.path.dirname(__file__)
BIN_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "bin"))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import clinfo_test


class TestClinfoTest(unittest.TestCase):
    @patch("clinfo_test.load_json_file")
    @patch("clinfo_test.build_command", return_value="/opt/custom-clinfo")
    def test_resolve_clinfo_command_from_json(
        self,
        mock_build_command,
        mock_load_json_file,
    ):
        mock_load_json_file.return_value = {
            "executable": {"bin": "clinfo"}
        }

        result = clinfo_test._resolve_clinfo_command("/tmp/cfg.json")

        self.assertEqual(result, "/opt/custom-clinfo")
        mock_load_json_file.assert_called_once_with(
            "/tmp/cfg.json", enable_logger=False
        )
        mock_build_command.assert_called_once_with(
            {"bin": "clinfo"}, enable_logger=False
        )

    @patch("clinfo_test.load_json_file", return_value={})
    def test_resolve_clinfo_command_invalid_executable_data(self, _mock_loader):
        result = clinfo_test._resolve_clinfo_command("/tmp/cfg.json")
        self.assertIsNone(result)

    @patch("clinfo_test.load_json_file")
    @patch("clinfo_test.build_command", side_effect=ValueError("bad config"))
    def test_resolve_clinfo_command_build_command_failure(
        self,
        _mock_build_command,
        mock_load_json_file,
    ):
        mock_load_json_file.return_value = {
            "executable": {"bin": "clinfo"}
        }

        result = clinfo_test._resolve_clinfo_command("/tmp/cfg.json")

        self.assertIsNone(result)

    @patch("clinfo_test.shutil.which", return_value=None)
    def test_resolve_clinfo_command_missing_system_clinfo(self, _mock_which):
        result = clinfo_test._resolve_clinfo_command("")
        self.assertIsNone(result)

    @patch("clinfo_test.shutil.which", return_value="/usr/bin/clinfo")
    def test_resolve_clinfo_command_uses_system_clinfo(self, _mock_which):
        result = clinfo_test._resolve_clinfo_command("")
        self.assertEqual(result, "/usr/bin/clinfo")

    @patch("clinfo_test.subprocess.run")
    def test_run_clinfo_command_uses_common_subprocess_options(self, mock_run):
        expected = subprocess.CompletedProcess(
            args="clinfo -v",
            returncode=0,
            stdout="v",
            stderr="",
        )
        mock_run.return_value = expected

        result = clinfo_test._run_clinfo_command("clinfo -v")

        self.assertEqual(result, expected)
        mock_run.assert_called_once_with(
            "clinfo -v",
            shell=True,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_parse_clinfo_list_output(self):
        output = (
            "Platform #0: ARM Platform\n"
            " `-- Device #0: Mali-G57 r0p0\n"
            "|-- Device #1: Mali-G57 r0p1\n"
        )

        records = clinfo_test.parse_clinfo_list_output(output)

        self.assertEqual(
            records,
            [
                {
                    "platform": "ARM Platform",
                    "platform_number": 0,
                    "device": "Mali-G57 r0p0",
                    "device_number": 0,
                },
                {
                    "platform": "ARM Platform",
                    "platform_number": 0,
                    "device": "Mali-G57 r0p1",
                    "device_number": 1,
                },
            ],
        )

    def test_parse_ignored_set_returns_empty_without_path(self):
        self.assertEqual(clinfo_test.parse_ignored_set(""), set())

    @patch("clinfo_test.load_json_file")
    def test_parse_ignored_set_filters_invalid_entries(self, mock_load_json_file):
        mock_load_json_file.return_value = {
            "ignored_set": {
                "platform-a": ["dev-a", "dev-b", 2],
                "platform-b": "not-a-list",
            }
        }

        result = clinfo_test.parse_ignored_set("/tmp/validation.json")

        self.assertEqual(
            result,
            {
                ("platform-a", "dev-a"),
                ("platform-a", "dev-b"),
            },
        )

    def test_parse_property_value(self):
        output = (
            "[ARM/0] CL_DEVICE_AVAILABLE CL_TRUE\n"
            "[ARM/0] CL_DEVICE_MAX_COMPUTE_UNITS 16\n"
        )

        self.assertEqual(
            clinfo_test.parse_property_value(output, "CL_DEVICE_AVAILABLE"),
            "CL_TRUE",
        )
        self.assertIsNone(
            clinfo_test.parse_property_value(output, "NO_SUCH_PROP")
        )

    def test_load_validation_set_uses_defaults_without_json(self):
        result = clinfo_test.load_validation_set("", "p", "d")
        self.assertEqual(result, clinfo_test.DEFAULT_VALIDATION_SET)

    @patch("clinfo_test.load_json_file")
    def test_load_validation_set_returns_defaults_when_missing_platform(
        self,
        mock_load_json_file,
    ):
        mock_load_json_file.return_value = {
            "customized_validation_set": {
                "other-platform": {"other-device": {"A": "B"}}
            }
        }

        result = clinfo_test.load_validation_set(
            "/tmp/validation.json",
            "platform",
            "device",
        )

        self.assertEqual(result, clinfo_test.DEFAULT_VALIDATION_SET)

    @patch("clinfo_test.load_json_file")
    def test_load_validation_set_merges_and_stringifies_values(
        self,
        mock_load_json_file,
    ):
        mock_load_json_file.return_value = {
            "customized_validation_set": {
                "platform": {
                    "device": {
                        "CL_DEVICE_AVAILABLE": "CL_FALSE",
                        "CL_DEVICE_MAX_COMPUTE_UNITS": 8,
                    }
                }
            }
        }

        result = clinfo_test.load_validation_set(
            "/tmp/validation.json",
            "platform",
            "device",
        )

        self.assertEqual(result["CL_DEVICE_AVAILABLE"], "CL_FALSE")
        self.assertEqual(result["CL_DEVICE_MAX_COMPUTE_UNITS"], "8")
        self.assertEqual(
            result["CL_DEVICE_COMPILER_AVAILABLE"],
            "CL_TRUE",
        )

    @patch("clinfo_test._resolve_clinfo_command", return_value=None)
    def test_cmd_detect_returns_1_when_command_cannot_resolve(
        self,
        _mock_resolve,
    ):
        self.assertEqual(clinfo_test.cmd_detect(""), 1)

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test._run_clinfo_command")
    def test_cmd_detect_returns_version_return_code_on_version_failure(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = subprocess.CompletedProcess(
            args="clinfo -v",
            returncode=9,
            stdout="",
            stderr="",
        )

        self.assertEqual(clinfo_test.cmd_detect(""), 9)

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test._run_clinfo_command")
    def test_cmd_detect_fails_without_platform(self, mock_run, _mock_resolve):
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args="clinfo -v",
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args="clinfo -l",
                returncode=0,
                stdout="Number of platforms 0\n",
                stderr="",
            ),
        ]

        self.assertEqual(clinfo_test.cmd_detect(""), 1)

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test._run_clinfo_command")
    def test_cmd_detect_fails_when_platform_has_no_device(
        self,
        mock_run,
        _mock_resolve,
    ):
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args="clinfo -v",
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args="clinfo -l",
                returncode=0,
                stdout="Platform #0: rusticl\n",
                stderr="",
            ),
        ]

        self.assertEqual(clinfo_test.cmd_detect(""), 1)

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test._run_clinfo_command")
    def test_cmd_detect_pass(self, mock_run, _mock_resolve):
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args="clinfo -v",
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args="clinfo -l",
                returncode=0,
                stdout=(
                    "Platform #0: ARM Platform\n"
                    " `-- Device #0: Mali-G57 r0p0\n"
                ),
                stderr="",
            ),
        ]

        self.assertEqual(clinfo_test.cmd_detect(""), 0)

    @patch("clinfo_test._resolve_clinfo_command", return_value=None)
    def test_cmd_resource_returns_1_when_command_cannot_resolve(
        self,
        _mock_resolve,
    ):
        self.assertEqual(clinfo_test.cmd_resource("", ""), 1)

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test._run_clinfo_command")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_cmd_resource_prints_records_and_ignore_flags(
        self,
        mock_stdout,
        mock_run,
        _mock_resolve,
    ):
        mock_run.return_value = subprocess.CompletedProcess(
            args="clinfo -l",
            returncode=0,
            stdout=(
                "Platform #0: ARM Platform\n"
                " `-- Device #0: DevA\n"
                "Platform #1: NVIDIA CUDA\n"
                " `-- Device #0: DevB\n"
            ),
            stderr="",
        )

        with patch(
            "clinfo_test.parse_ignored_set",
            return_value={("NVIDIA CUDA", "DevB")},
        ):
            result = clinfo_test.cmd_resource("", "/tmp/validation.json")

        output = mock_stdout.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("platform: ARM Platform", output)
        self.assertIn("device: DevA", output)
        self.assertIn("ignore: false", output)
        self.assertIn("platform: NVIDIA CUDA", output)
        self.assertIn("device: DevB", output)
        self.assertIn("ignore: true", output)

    @patch("clinfo_test._resolve_clinfo_command", return_value=None)
    def test_cmd_test_returns_1_when_command_cannot_resolve(
        self,
        _mock_resolve,
    ):
        result = clinfo_test.cmd_test(
            "",
            "",
            "platform",
            0,
            "device",
            0,
        )
        self.assertEqual(result, 1)

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test.load_validation_set")
    @patch("clinfo_test._run_clinfo_command")
    def test_cmd_test_fails_on_property_mismatch(
        self,
        mock_run,
        mock_load_validation_set,
        _mock_resolve,
    ):
        mock_load_validation_set.return_value = {
            "CL_DEVICE_AVAILABLE": "CL_TRUE"
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args="clinfo -d 0:0 --prop CL_DEVICE_AVAILABLE",
            returncode=0,
            stdout="CL_DEVICE_AVAILABLE CL_FALSE\n",
            stderr="",
        )

        result = clinfo_test.cmd_test(
            "",
            "",
            "platform",
            0,
            "device",
            0,
        )

        self.assertEqual(result, 1)
        self.assertIn("-d 0:0", mock_run.call_args[0][0])

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test.load_validation_set")
    @patch("clinfo_test._run_clinfo_command")
    def test_cmd_test_fails_on_subcommand_error(
        self,
        mock_run,
        mock_load_validation_set,
        _mock_resolve,
    ):
        mock_load_validation_set.return_value = {
            "CL_DEVICE_AVAILABLE": "CL_TRUE"
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args="clinfo -d 0:0 --prop CL_DEVICE_AVAILABLE",
            returncode=4,
            stdout="",
            stderr="device error",
        )

        result = clinfo_test.cmd_test(
            "",
            "",
            "platform",
            0,
            "device",
            0,
        )

        self.assertEqual(result, 1)

    @patch("clinfo_test._resolve_clinfo_command", return_value="clinfo")
    @patch("clinfo_test.load_validation_set")
    @patch("clinfo_test._run_clinfo_command")
    def test_cmd_test_passes_with_all_properties_matching(
        self,
        mock_run,
        mock_load_validation_set,
        _mock_resolve,
    ):
        validation_set = {
            "CL_DEVICE_AVAILABLE": "CL_TRUE",
            "CL_DEVICE_COMPILER_AVAILABLE": "CL_TRUE",
        }
        mock_load_validation_set.return_value = validation_set

        def side_effect(command, capture_output=True):
            prop_name = command.rsplit(" ", 1)[1]
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout="{} {}\n".format(prop_name, validation_set[prop_name]),
                stderr="",
            )

        mock_run.side_effect = side_effect

        result = clinfo_test.cmd_test(
            "",
            "",
            "platform",
            2,
            "device",
            3,
        )

        self.assertEqual(result, 0)

    @patch("clinfo_test.cmd_detect", return_value=7)
    @patch("sys.argv", ["clinfo_test.py", "detect"]) 
    def test_main_routes_detect(self, mock_cmd_detect):
        self.assertEqual(clinfo_test.main(), 7)
        mock_cmd_detect.assert_called_once_with("")

    @patch("clinfo_test.cmd_resource", return_value=8)
    @patch("sys.argv", ["clinfo_test.py", "resource"]) 
    def test_main_routes_resource(self, mock_cmd_resource):
        self.assertEqual(clinfo_test.main(), 8)
        mock_cmd_resource.assert_called_once_with("", "")

    @patch("clinfo_test.cmd_test", return_value=9)
    @patch(
        "sys.argv",
        [
            "clinfo_test.py",
            "test",
            "-p",
            "p",
            "-pn",
            "1",
            "-d",
            "d",
            "-dn",
            "2",
        ],
    )
    def test_main_routes_test(self, mock_cmd_test):
        self.assertEqual(clinfo_test.main(), 9)
        mock_cmd_test.assert_called_once_with("", "", "p", "1", "d", "2")

    @patch("clinfo_test.logger")
    @patch("sys.argv", ["clinfo_test.py", "detect", "--debug"])
    @patch("clinfo_test.cmd_detect", return_value=0)
    def test_main_debug_enables_debug_logging(
        self,
        _mock_cmd_detect,
        mock_logger,
    ):
        self.assertEqual(clinfo_test.main(), 0)
        mock_logger.setLevel.assert_called_once_with(clinfo_test.logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
