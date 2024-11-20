#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Eugene Wu <eugene.wu@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from wol_server import (
    app,
    tasker_main,
    send_wol_command,
    is_pingable,
    run_task,
)
import subprocess

client = TestClient(app)


class TestMainFunction(unittest.TestCase):

    def setUp(self):
        self.wol_info = {
            "DUT_MAC": "00:11:22:33:44:55",
            "DUT_IP": "192.168.1.1",
            "delay": 10,
            "retry_times": 3,
            "wake_type": "g",
        }
        self.pingable_data = {
            "DUT_MAC": "00:11:22:33:44:55",
            "DUT_IP": "192.168.1.1",
            "delay": 1,
            "retry_times": 2,
            "wake_type": "g",
        }

    @patch("wol_server.tasker_main")
    def test_testing_endpoint_success(self, mock_tasker_main):
        mock_tasker_main.return_value = {"result": "success"}
        response = client.post("/", json=self.wol_info)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": "success"})

    @patch("wol_server.tasker_main")
    @patch("wol_server.logger")
    def test_testing_endpoint_exception(self, mock_logger, mock_tasker_main):
        mock_tasker_main.side_effect = Exception("Simulated exception")
        response = client.post("/", json=self.wol_info)
        self.assertEqual(response.status_code, 500)
        mock_logger.error.assert_called_with(
            "exception in testing: Simulated exception"
        )

    @patch("wol_server.logger")
    @patch("wol_server.subprocess.check_output")
    def test_send_wol_command_success(self, mock_check_output, mock_logger):
        mock_check_output.return_value = b"Command output"
        result = send_wol_command(self.wol_info)
        self.assertTrue(result)
        mock_check_output.assert_called_once_with(
            ["wakeonlan", self.wol_info["DUT_MAC"]]
        )
        mock_logger.debug.assert_any_call(
            f"Wake on lan command: wakeonlan {self.wol_info['DUT_MAC']}"
        )

    @patch("wol_server.logger")
    @patch("wol_server.subprocess.check_output")
    def test_send_wol_command_failure(self, mock_check_output, mock_logger):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "cmd")
        result = send_wol_command(self.wol_info)
        self.assertFalse(result)
        mock_logger.error.assert_called_once_with(
            "Error occurred in tasker_main: "
            "Command 'cmd' returned non-zero exit status 1."
        )

    @patch("wol_server.subprocess.check_output")
    def test_is_pingable_success(self, mock_check_output):
        mock_check_output.return_value = b"Ping output"
        result = is_pingable(self.wol_info["DUT_IP"])
        self.assertTrue(result)
        mock_check_output.assert_called_once_with(
            ["ping", "-c", "1", "-W", "1", self.wol_info["DUT_IP"]],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

    @patch("wol_server.subprocess.check_output")
    def test_is_pingable_failure(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "cmd")
        result = is_pingable(self.wol_info["DUT_IP"])
        self.assertFalse(result)
        mock_check_output.assert_called_once()

    @patch("wol_server.threading.Thread")
    @patch("wol_server.logger")
    def test_tasker_main_success(self, mock_logger, mock_thread):
        result = tasker_main(self.wol_info)
        self.assertEqual(result, {"result": "success"})
        mock_logger.info.assert_any_call(f"Received request: {self.wol_info}")
        mock_thread.assert_called_once()

    @patch("wol_server.logger")
    def test_tasker_main_missing_fields(self, mock_logger):
        incomplete_request = {"DUT_MAC": "00:11:22:33:44:55"}
        result = tasker_main(incomplete_request)
        self.assertEqual(
            result, {"result": "error", "message": "Missing required fields"}
        )
        mock_logger.error.assert_any_call(
            "Missing required fields: DUT_IP or delay"
        )

    @patch("wol_server.send_wol_command")
    @patch("wol_server.is_pingable")
    @patch("wol_server.time.sleep", return_value=None)
    @patch("wol_server.logger")
    def test_run_task_success(
        self, mock_logger, mock_sleep, mock_is_pingable, mock_send_wol_command
    ):
        mock_send_wol_command.return_value = True
        mock_is_pingable.return_value = True
        result = run_task(self.pingable_data, self.pingable_data["delay"])
        self.assertTrue(result)
        mock_send_wol_command.assert_called()
        mock_is_pingable.assert_called()

    @patch("wol_server.send_wol_command")
    @patch("wol_server.is_pingable")
    @patch("wol_server.time.sleep", return_value=None)
    @patch("wol_server.logger")
    def test_run_task_failure(
        self, mock_logger, mock_sleep, mock_is_pingable, mock_send_wol_command
    ):
        mock_send_wol_command.return_value = True
        mock_is_pingable.return_value = False
        result = run_task(self.pingable_data, self.pingable_data["delay"])
        self.assertFalse(result)
        mock_send_wol_command.assert_called()
        mock_is_pingable.assert_called()

    @patch("wol_server.logger")
    @patch("wol_server.threading.Thread")
    def test_tasker_main_exception(self, mock_thread, mock_logger):
        mock_thread.side_effect = Exception("Simulated exception")
        result = tasker_main(self.wol_info)
        self.assertEqual(
            result, {"result": "error", "message": "Simulated exception"}
        )
        mock_logger.error.assert_called_once_with(
            "Error occurred while processing the request: Simulated exception"
        )

    @patch("wol_server.time.sleep", return_value=None)
    @patch("wol_server.is_pingable")
    @patch("wol_server.send_wol_command")
    @patch("wol_server.logger")
    def test_run_task_exception(
        self, mock_logger, mock_send_wol_command, mock_is_pingable, mock_sleep
    ):
        mock_send_wol_command.side_effect = Exception("Simulated exception")

        result = run_task(self.pingable_data, self.pingable_data["delay"])

        self.assertFalse(result)
        mock_logger.error.assert_called_with(
            "Error occurred in tasker_main: Simulated exception"
        )
        mock_send_wol_command.assert_called()
        mock_sleep.assert_called()


if __name__ == "__main__":
    unittest.main()
