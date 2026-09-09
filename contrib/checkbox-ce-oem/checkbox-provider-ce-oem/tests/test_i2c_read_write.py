import subprocess
import unittest
from unittest.mock import call, patch

import i2c_read_write


class TestExecuteWriteStep(unittest.TestCase):
    @patch("i2c_read_write._run_i2c_transfer")
    def test_write_step_with_data_calls_transfer(self, mock_run):
        step = {
            "data": ["0x11", "0x22"],
        }

        result = i2c_read_write._execute_write_step(
            step,
            i2c_bus=10,
            chip_address="0x50",
            reg_address=["0x00", "0x00"],
            variables={},
        )

        self.assertTrue(result)
        mock_run.assert_called_once_with(
            10,
            ["w4@0x50 0x00 0x00 0x11 0x22"],
        )

    @patch("i2c_read_write._run_i2c_transfer")
    def test_write_step_with_data_from_variable_calls_transfer(self, mock_run):
        step = {
            "data_from_variable": "cached_data",
        }
        variables = {"cached_data": ["0xaa", "0xbb"]}

        result = i2c_read_write._execute_write_step(
            step,
            i2c_bus=2,
            chip_address="0x51",
            reg_address=["0x10"],
            variables=variables,
        )

        self.assertTrue(result)
        mock_run.assert_called_once_with(
            2,
            ["w3@0x51 0x10 0xaa 0xbb"],
        )

    @patch("i2c_read_write._run_i2c_transfer")
    def test_write_step_rejects_missing_data_and_variable(self, mock_run):
        result = i2c_read_write._execute_write_step(
            {},
            i2c_bus=1,
            chip_address="0x50",
            reg_address=[],
            variables={},
        )

        self.assertFalse(result)
        mock_run.assert_not_called()

    @patch("i2c_read_write._run_i2c_transfer")
    def test_write_step_rejects_undefined_data_from_variable(self, mock_run):
        step = {"data_from_variable": "missing"}

        result = i2c_read_write._execute_write_step(
            step,
            i2c_bus=1,
            chip_address="0x50",
            reg_address=[],
            variables={},
        )

        self.assertFalse(result)
        mock_run.assert_not_called()


class TestExecuteReadStep(unittest.TestCase):
    @patch("i2c_read_write._run_i2c_transfer")
    def test_read_step_with_expected_output_and_save_variable(self, mock_run):
        step = {
            "read_length": 4,
            "expected_output": ["0x11", "0x22", "0x33", "0x44"],
            "save_to_variable": "read_back",
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="0x11 0x22 0x33 0x44\n",
        )
        variables = {}

        result = i2c_read_write._execute_read_step(
            step,
            i2c_bus=10,
            chip_address="0x50",
            reg_address=["0x00", "0x00"],
            variables=variables,
        )

        self.assertTrue(result)
        self.assertEqual(
            variables,
            {"read_back": ["0x11", "0x22", "0x33", "0x44"]},
        )
        mock_run.assert_called_once_with(
            10,
            ["w2@0x50 0x00 0x00", "r4@0x50"],
        )

    @patch("i2c_read_write._run_i2c_transfer")
    def test_read_step_fails_when_output_shorter_than_read_length(
        self, mock_run
    ):
        step = {"read_length": 4}
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="0x11 0x22\n",
        )

        result = i2c_read_write._execute_read_step(
            step,
            i2c_bus=10,
            chip_address="0x50",
            reg_address=[],
            variables={},
        )

        self.assertFalse(result)
        mock_run.assert_called_once_with(10, ["r4@0x50"])

    @patch("i2c_read_write._run_i2c_transfer")
    def test_read_step_fails_on_expected_output_mismatch(self, mock_run):
        step = {
            "read_length": 2,
            "expected_output": ["0xaa", "0xbb"],
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="0xaa 0xcc\n",
        )

        result = i2c_read_write._execute_read_step(
            step,
            i2c_bus=3,
            chip_address="0x51",
            reg_address=[],
            variables={},
        )

        self.assertFalse(result)
        mock_run.assert_called_once_with(3, ["r2@0x51"])


class TestCmdTestScenarios(unittest.TestCase):
    @patch("i2c_read_write._run_i2c_transfer")
    @patch("i2c_read_write.get_i2c_scenarios")
    def test_write_then_read_same_device(self, mock_get_scenarios, mock_run):
        scenario_name = "same-device"
        mock_get_scenarios.return_value = {
            scenario_name: {
                "steps": [
                    {
                        "description": "write bytes",
                        "operation": "write",
                        "i2c_bus": 10,
                        "chip_address": "0x50",
                        "reg_address": ["0x00", "0x00"],
                        "data": ["0x11", "0x22", "0x33", "0x44"],
                    },
                    {
                        "description": "read same bytes",
                        "operation": "read",
                        "i2c_bus": 10,
                        "chip_address": "0x50",
                        "reg_address": ["0x00", "0x00"],
                        "read_length": 4,
                        "expected_output": [
                            "0x11",
                            "0x22",
                            "0x33",
                            "0x44",
                        ],
                    },
                ]
            }
        }
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=""),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="0x11 0x22 0x33 0x44\n",
            ),
        ]

        result = i2c_read_write.cmd_test(scenario_name)

        self.assertEqual(result, 0)
        self.assertEqual(
            mock_run.call_args_list,
            [
                call(
                    10,
                    ["w6@0x50 0x00 0x00 0x11 0x22 0x33 0x44"],
                ),
                call(
                    10,
                    ["w2@0x50 0x00 0x00", "r4@0x50"],
                ),
            ],
        )

    @patch("i2c_read_write._run_i2c_transfer")
    @patch("i2c_read_write.get_i2c_scenarios")
    def test_write_then_read_different_device(
        self, mock_get_scenarios, mock_run
    ):
        scenario_name = "cross-device"
        mock_get_scenarios.return_value = {
            scenario_name: {
                "steps": [
                    {
                        "description": "write source bytes",
                        "operation": "write",
                        "i2c_bus": 10,
                        "chip_address": "0x50",
                        "reg_address": ["0x00", "0x00"],
                        "data": ["0xaa", "0xbb", "0xcc", "0xdd"],
                    },
                    {
                        "description": "read from target device",
                        "operation": "read",
                        "i2c_bus": 10,
                        "chip_address": "0x51",
                        "reg_address": ["0x00", "0x00"],
                        "read_length": 4,
                        "expected_output": [
                            "0xaa",
                            "0xbb",
                            "0xcc",
                            "0xdd",
                        ],
                    },
                ]
            }
        }
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=""),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="0xaa 0xbb 0xcc 0xdd\n",
            ),
        ]

        result = i2c_read_write.cmd_test(scenario_name)

        self.assertEqual(result, 0)
        self.assertEqual(
            mock_run.call_args_list,
            [
                call(
                    10,
                    ["w6@0x50 0x00 0x00 0xaa 0xbb 0xcc 0xdd"],
                ),
                call(
                    10,
                    ["w2@0x51 0x00 0x00", "r4@0x51"],
                ),
            ],
        )
