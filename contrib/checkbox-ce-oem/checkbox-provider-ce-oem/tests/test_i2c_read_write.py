import subprocess
import unittest
from unittest.mock import patch

import i2c_read_write


class TestRunI2CTransfer(unittest.TestCase):
    @patch("i2c_read_write.subprocess.run")
    def test_write_message_is_split_into_tokens(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        i2c_read_write._run_i2c_transfer(
            10,
            ["w6@0x50 0x00 0x00 0x11 0x22 0x33 0x44"],
        )

        mock_run.assert_called_once_with(
            [
                "i2ctransfer",
                "-y",
                "10",
                "w6@0x50",
                "0x00",
                "0x00",
                "0x11",
                "0x22",
                "0x33",
                "0x44",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    @patch("i2c_read_write.subprocess.run")
    def test_multiple_messages_are_split_into_tokens(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="0x11 0x22 0x33 0x44\n",
            stderr="",
        )

        i2c_read_write._run_i2c_transfer(
            10,
            ["w2@0x50 0x00 0x00", "r4@0x50"],
        )

        mock_run.assert_called_once_with(
            [
                "i2ctransfer",
                "-y",
                "10",
                "w2@0x50",
                "0x00",
                "0x00",
                "r4@0x50",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    @patch("i2c_read_write.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_i2ctransfer_raises_runtime_error(self, _mock_run):
        with self.assertRaisesRegex(RuntimeError, "command not found"):
            i2c_read_write._run_i2c_transfer(1, ["w1@0x50 0x00"])
