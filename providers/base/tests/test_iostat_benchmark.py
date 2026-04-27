import subprocess
import unittest
from io import StringIO
from unittest.mock import patch

import iostat_benchmark

IOSTAT_OUTPUT = """\
Linux 6.8.0-57-generic (hostname)	04/27/2026	_x86_64_	(8 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           0.50    0.00    0.25    0.10    0.00   99.15

Device            r/s     rMB/s   rrqm/s  %rrqm r_await rareq-sz     w/s     wMB/s   wrqm/s  %wrqm w_await wareq-sz     d/s     dMB/s   drqm/s  %drqm d_await dareq-sz     f/s f_await  aqu-sz  %util
sda              0.10      0.00     0.00   0.00    0.50    10.00    1.00      0.01     0.50  33.33    5.00    10.24    0.00      0.00     0.00   0.00    0.00     0.00    0.00    0.00    0.01   0.10

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           0.60    0.00    0.30    0.05    0.00   99.05

Device            r/s     rMB/s   rrqm/s  %rrqm r_await rareq-sz     w/s     wMB/s   wrqm/s  %wrqm w_await wareq-sz     d/s     dMB/s   drqm/s  %drqm d_await dareq-sz     f/s f_await  aqu-sz  %util
sda              0.00      0.00     0.00   0.00    0.00     0.00    0.50      0.00     0.25  33.33    4.00     8.00    0.00      0.00     0.00   0.00    0.00     0.00    0.00    0.00    0.00   0.20

"""


class TestParseIostatColumn(unittest.TestCase):
    def test_cpu_idle_average(self):
        out = StringIO()
        with patch("sys.stdout", out):
            ret = iostat_benchmark.parse_iostat_column(IOSTAT_OUTPUT, "idle")
        self.assertEqual(ret, 0)
        # (99.15 + 99.05) / 2 = 99.1
        self.assertIn("99.1", out.getvalue())

    def test_disk_util_average(self):
        out = StringIO()
        with patch("sys.stdout", out):
            ret = iostat_benchmark.parse_iostat_column(IOSTAT_OUTPUT, "util")
        self.assertEqual(ret, 0)
        # (0.10 + 0.20) / 2 = 0.15
        self.assertIn("0.15", out.getvalue())

    def test_missing_column_returns_error(self):
        err = StringIO()
        with patch("sys.stderr", err):
            ret = iostat_benchmark.parse_iostat_column(
                "no output here", "idle"
            )
        self.assertEqual(ret, 1)
        self.assertIn("idle", err.getvalue())


class TestMain(unittest.TestCase):
    @patch(
        "iostat_benchmark.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=IOSTAT_OUTPUT
        ),
    )
    def test_main_cpu(self, mock_run):
        out = StringIO()
        with patch("sys.stdout", out), patch(
            "sys.argv", ["iostat_benchmark.py", "cpu"]
        ):
            ret = iostat_benchmark.main()
        self.assertEqual(ret, 0)
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["iostat", "-x", "-m", "1", "10"])
        self.assertTrue(kwargs.get("check"))
        self.assertTrue(
            (
                kwargs.get("capture_output") is True
                and kwargs.get("text") is True
            )
            or (
                kwargs.get("stdout") == subprocess.PIPE
                and kwargs.get("stderr") == subprocess.PIPE
                and kwargs.get("universal_newlines") is True
            )
        )

    @patch(
        "iostat_benchmark.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=IOSTAT_OUTPUT
        ),
    )
    def test_main_disk(self, mock_run):
        out = StringIO()
        with patch("sys.stdout", out), patch(
            "sys.argv", ["iostat_benchmark.py", "disk"]
        ):
            ret = iostat_benchmark.main()
        self.assertEqual(ret, 0)

    @patch(
        "iostat_benchmark.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "iostat"),
    )
    def test_main_iostat_failure(self, _mock_run):
        err = StringIO()
        with patch("sys.stderr", err), patch(
            "sys.argv", ["iostat_benchmark.py", "cpu"]
        ):
            ret = iostat_benchmark.main()
        self.assertEqual(ret, 1)
        self.assertIn("iostat failed", err.getvalue())


if __name__ == "__main__":
    unittest.main()
