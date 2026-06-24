#!/usr/bin/env python3

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from subprocess import CalledProcessError
import textwrap
from unittest.mock import call, patch
import memory_compare


class MemoryCompareTests(unittest.TestCase):

    GiB = 1024**3
    MiB = 1024**2

    def run_main(self, installed, visible, igpu_vram):
        stdout = StringIO()
        stderr = StringIO()
        with patch("memory_compare.os.geteuid", return_value=0):
            with patch(
                "memory_compare.get_installed_memory_size",
                return_value=installed,
            ):
                with patch(
                    "memory_compare.get_visible_memory_size",
                    return_value=visible,
                ):
                    with patch(
                        "memory_compare.get_igpu_vram_size",
                        return_value=igpu_vram,
                    ):
                        with redirect_stdout(stdout), redirect_stderr(stderr):
                            result = memory_compare.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_main_keeps_existing_behavior_without_vram(self):
        installed = 16 * self.GiB
        visible = int(15.42 * self.GiB)

        result, stdout, stderr = self.run_main(installed, visible, 0)

        self.assertEqual(result, 0)
        self.assertIn("PASS: Meminfo reports", stdout)
        self.assertNotIn("iGPU VRAM compensation", stdout)
        self.assertEqual(stderr, "")

    def test_main_compensates_igpu_vram_before_threshold_check(self):
        installed = 8 * self.GiB
        visible = installed - 2503073792
        igpu_vram = 2048 * self.MiB

        result, stdout, stderr = self.run_main(installed, visible, igpu_vram)

        self.assertEqual(result, 0)
        self.assertIn("iGPU VRAM compensation:\t2GiB", stdout)
        self.assertIn("difference of 4.14%", stdout)
        self.assertEqual(stderr, "")

    def test_adjusted_difference_is_never_negative(self):
        installed = 8 * self.GiB
        visible = installed - 512 * self.MiB
        igpu_vram = 2048 * self.MiB

        self.assertEqual(
            memory_compare.get_adjusted_memory_difference(
                installed, visible, igpu_vram
            ),
            0,
        )

    def test_zero_memory_error_stays_unchanged(self):
        result, stdout, stderr = self.run_main(0, 0, 2048 * self.MiB)

        self.assertEqual(result, 1)
        self.assertEqual(stdout, "Results:\n")
        self.assertIn("returned a size of 0 kB", stderr)

    def test_kernel_log_parser_prefers_used_vram(self):
        kernel_log = textwrap.dedent("""\
            [0.824195] rtc_cmos 00:01: alarms up to one month, 114 bytes nvram
            [2.870716] amdgpu 00:03:00.0: amdgpu: VRAM: 2048M 0x0 (2048M used)
            [2.870727] [drm] Detected VRAM RAM=4096M, BAR=4096M
            [2.871060] [drm] amdgpu: 2048M of VRAM memory ready
        """)

        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(
                memory_compare.get_igpu_vram_size_from_kernel_log(kernel_log),
                2048 * self.MiB,
            )
        self.assertIn("Detected VRAM size", stdout.getvalue())

    def test_kernel_log_parser_returns_zero_without_used_vram(self):
        kernel_log = textwrap.dedent("""\
            [    2.870727] [drm] Detected VRAM RAM=4096M, BAR=4096M
            [    2.871060] [drm] amdgpu: 4096M of VRAM memory ready
        """)

        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(
                memory_compare.get_igpu_vram_size_from_kernel_log(kernel_log),
                0,
            )
        self.assertIn("Detected VRAM size", stdout.getvalue())

    @patch("memory_compare.MeminfoParser")
    def test_visible_memory_size_uses_meminfo_total(self, mock_parser):
        parser = mock_parser.return_value
        parser.run.return_value = {"total": 123456789}

        self.assertEqual(memory_compare.get_visible_memory_size(), 123456789)
        mock_parser.assert_called_once_with()
        parser.run.assert_called_once_with()

    @patch("memory_compare.check_output")
    def test_vram_detection_uses_journalctl_grep_context(
        self, mock_check_output
    ):
        journal = "full kernel log with VRAM somewhere"
        vram_output = (
            "before context\n"
            "amdgpu 0000:65:00.0: amdgpu: "
            "VRAM: 4096M 0x0 (4096M used)\n"
            "after context"
        )
        mock_check_output.side_effect = [journal, vram_output]

        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(
                memory_compare.get_igpu_vram_size(),
                4096 * self.MiB,
            )
        mock_check_output.assert_has_calls(
            [
                call(
                    ["journalctl", "-k", "-b", "--no-pager"],
                    universal_newlines=True,
                ),
                call(
                    ["grep", "-C10", "VRAM"],
                    input=journal,
                    universal_newlines=True,
                ),
            ]
        )
        self.assertIn("Kernel VRAM log output:", stdout.getvalue())
        self.assertIn("before context", stdout.getvalue())
        self.assertIn("VRAM: 4096M", stdout.getvalue())
        self.assertIn("after context", stdout.getvalue())

    @patch("memory_compare.check_output")
    def test_vram_detection_returns_zero_without_output(
        self, mock_check_output
    ):
        mock_check_output.side_effect = [
            "kernel log without vram",
            CalledProcessError(1, ["grep", "-C10", "VRAM"]),
        ]

        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(memory_compare.get_igpu_vram_size(), 0)
        self.assertIn("No VRAM log output found", stdout.getvalue())

    @patch("memory_compare.check_output")
    def test_vram_detection_returns_zero_when_journalctl_fails(
        self, mock_check_output
    ):
        mock_check_output.side_effect = CalledProcessError(
            1, ["journalctl", "-k", "-b", "--no-pager"]
        )

        stderr = StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(memory_compare.get_igpu_vram_size(), 0)
        self.assertIn("Failed to get kernel log output:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
