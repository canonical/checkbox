import subprocess
import unittest
from unittest.mock import patch, MagicMock
import serialcheck as sc


class TestSerialCheck(unittest.TestCase):

    @patch("serialcheck.subprocess.run")
    def test_runcmd(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="output", stderr="error", returncode=0
        )
        result = sc.runcmd("echo Hello")

        mock_run.assert_called_once_with(
            "echo Hello",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        self.assertEqual(result.stdout, "output")
        self.assertEqual(result.stderr, "error")
        self.assertEqual(result.returncode, 0)

    @patch("serialcheck.runcmd")
    @patch("os.environ.get")
    def test_uart_by_sc(self, mock_get, mock_runcmd):
        mock_get.return_value = "/tmp"

        # Mock the runcmd function to return the correct message
        msg = (
            "cts: 0 dsr: 0 rng: 0 dcd: 0 rx: 12288 "
            "tx: 12288 frame 0 ovr 0 par: 0 brk: 0 buf_ovrr: 0\n"
        )
        # The first command is to copy the file, so we don't need the output
        results = [""] + [MagicMock(stdout=msg, stderr="", returncode=0)] * 17
        mock_runcmd.side_effect = results

        self.assertEqual(sc.test_uart_by_serialcheck("mt8390"), None)
        mock_runcmd.assert_called_with(
            [
                "genio-test-tool.serialcheck -d /dev/ttyS2 -f /tmp/binary "
                "-m d -l 3 -b 110"
            ],
        )

    @patch("serialcheck.runcmd")
    @patch("os.environ.get")
    def test_uart_by_sc_mt8395(self, mock_get, mock_runcmd):
        mock_get.return_value = "/tmp"

        # Mock the runcmd function to return the correct message
        msg = (
            "cts: 0 dsr: 0 rng: 0 dcd: 0 rx: 12288 "
            "tx: 12288 frame 0 ovr 0 par: 0 brk: 0 buf_ovrr: 0\n"
        )
        # The first command is to copy the file, so we don't need the output
        results = [""] + [MagicMock(stdout=msg, stderr="", returncode=0)] * 17
        mock_runcmd.side_effect = results

        self.assertEqual(sc.test_uart_by_serialcheck("mt8395"), None)
        mock_runcmd.assert_called_with(
            [
                "genio-test-tool.serialcheck -d /dev/ttyS1 -f /tmp/binary "
                "-m d -l 3 -b 110"
            ],
        )

    @patch("serialcheck.runcmd")
    @patch("os.environ.get")
    def test_uart_by_sc_bad_return_code(self, mock_get, mock_runcmd):
        mock_get.return_value = "/tmp"

        # Mock the runcmd function to return a wrong message
        msg = (
            "cts: 0 dsr: 0 rng: 0 dcd: 0 rx: 12288 "
            "tx: 12288 frame 0 ovr 0 par: 0 brk: 0 buf_ovrr: 0\n"
        )
        # The first command is to copy the file, so we don't need the output
        results = [""] + [MagicMock(stdout=msg, stderr="", returncode=1)] * 17
        mock_runcmd.side_effect = results

        with self.assertRaises(SystemExit):
            sc.test_uart_by_serialcheck("mt8395")

    @patch("serialcheck.runcmd")
    @patch("os.environ.get")
    def test_uart_by_sc_wrong_output(self, mock_get, mock_runcmd):
        mock_get.return_value = "/tmp"

        # Mock the runcmd function to return a wrong message
        msg = "output\nBad message\nend output"
        # The first command is to copy the file, so we don't need the output
        results = [""] + [MagicMock(stdout=msg, stderr="", returncode=0)] * 17
        mock_runcmd.side_effect = results

        with self.assertRaises(SystemExit):
            sc.test_uart_by_serialcheck("mt8395")

    @patch("serialcheck.test_uart_by_serialcheck")
    def test_main(self, mock_serialcheck):
        mock_serialcheck.return_value = 0
        with patch("sys.argv", ["script_name", "mt8395"]):
            result = sc.main()
        self.assertEqual(mock_serialcheck.call_count, 1)
        self.assertEqual(result, None)

    @patch("serialcheck.test_uart_by_serialcheck")
    def test_main_bad_args(self, mock_serialcheck):
        mock_serialcheck.return_value = 1
        with patch("sys.argv", ["script_name", "bad_soc"]):
            with self.assertRaises(SystemExit):
                sc.main()
        mock_serialcheck.assert_not_called()

    @patch("serialcheck.test_uart_by_serialcheck")
    def test_main_wrong_serialcheck(self, mock_serialcheck):
        mock_serialcheck.side_effect = SystemExit(1)
        with patch("sys.argv", ["script_name", "mt8395"]):
            with self.assertRaises(SystemExit):
                sc.main()
        self.assertEqual(mock_serialcheck.call_count, 1)
