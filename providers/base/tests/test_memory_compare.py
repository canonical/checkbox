#!/usr/bin/env python3

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from subprocess import CalledProcessError
import textwrap
from unittest.mock import call, mock_open, patch
import memory_compare


class MemoryCompareTests(unittest.TestCase):

    @patch("memory_compare.compare_memory")
    @patch("memory_compare.get_kexec_crash_size")
    @patch("memory_compare.get_igpu_vram_size")
    @patch("memory_compare.get_visible_memory_size")
    @patch("memory_compare.get_installed_memory_size")
    @patch("memory_compare.os.geteuid", return_value=0)
    def test_main_passes_collected_memory_values_to_compare_memory(
        self,
        mock_geteuid,
        mock_installed,
        mock_visible,
        mock_vram,
        mock_kexec_crash_size,
        mock_compare_memory,
    ):
        mock_installed.return_value = 1
        mock_visible.return_value = 2
        mock_vram.return_value = 3
        mock_kexec_crash_size.return_value = 4
        mock_compare_memory.return_value = 0

        self.assertEqual(memory_compare.main(), 0)
        mock_compare_memory.assert_called_once_with(1, 2, 3, 4)

    def compare_memory(self, installed, visible, igpu_vram, kexec_crash_size):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = memory_compare.compare_memory(
                installed, visible, igpu_vram, kexec_crash_size
            )
        return result, stdout.getvalue(), stderr.getvalue()

    def test_compare_memory_keeps_existing_behavior_without_vram(self):
        installed = memory_compare.HumanReadableBytes("16GiB")
        visible = int(installed * 15.42 / 16)

        result, stdout, stderr = self.compare_memory(installed, visible, 0, 0)

        self.assertEqual(result, 0)
        self.assertIn("PASS: Meminfo reports", stdout)
        self.assertNotIn("iGPU VRAM compensation", stdout)
        self.assertEqual(stderr, "")

    def test_compare_memory_compensates_igpu_vram_before_threshold_check(self):
        installed = memory_compare.HumanReadableBytes("8GiB")
        visible = installed - 2503073792
        igpu_vram = memory_compare.HumanReadableBytes("2048MiB")

        result, stdout, stderr = self.compare_memory(
            installed, visible, igpu_vram, 0
        )

        self.assertEqual(result, 0)
        self.assertIn("iGPU VRAM compensation:\t2GiB", stdout)
        self.assertIn("difference of 4.14%", stdout)
        self.assertEqual(stderr, "")

    def test_compare_memory_compensates_kexec_memory_before_threshold_check(
        self,
    ):
        installed = memory_compare.HumanReadableBytes("8GiB")
        visible = memory_compare.HumanReadableBytes("6GiB")
        igpu_vram = memory_compare.HumanReadableBytes("512MiB")
        kexec_crash_size = memory_compare.HumanReadableBytes("512MiB")

        result, stdout, stderr = self.compare_memory(
            installed, visible, igpu_vram, kexec_crash_size
        )

        self.assertEqual(result, 0)
        self.assertIn(
            "kexec crash memory compensation:\t512MiB",
            stdout,
        )
        self.assertIn("difference of 12.50%", stdout)
        self.assertEqual(stderr, "")

    def test_compare_memory_fails_when_difference_exceeds_threshold(self):
        installed = memory_compare.HumanReadableBytes("32GiB")
        visible = memory_compare.HumanReadableBytes("24GiB")
        igpu_vram = memory_compare.HumanReadableBytes("2GiB")
        kexec_crash_size = memory_compare.HumanReadableBytes("512MiB")

        result, stdout, stderr = self.compare_memory(
            installed, visible, igpu_vram, kexec_crash_size
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Results:", stderr)
        self.assertIn("/proc/meminfo reports:\t24GiB", stderr)
        self.assertIn("lshw reports:\t32GiB", stderr)
        self.assertIn("iGPU VRAM compensation:\t2GiB", stderr)
        self.assertIn("kexec crash memory compensation:\t512MiB", stderr)
        self.assertIn("Only a variance of 10% in reported memory", stderr)

    def test_adjusted_difference_is_never_negative(self):
        installed = memory_compare.HumanReadableBytes("8GiB")
        visible = installed - memory_compare.HumanReadableBytes("512MiB")
        reserved = memory_compare.HumanReadableBytes("2048MiB")

        self.assertEqual(
            memory_compare.get_adjusted_memory_difference(
                installed, visible, reserved
            ),
            0,
        )

    def test_zero_memory_error_stays_unchanged(self):
        igpu_vram = memory_compare.HumanReadableBytes("2048MiB")

        result, stdout, stderr = self.compare_memory(0, 0, igpu_vram, 0)

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
                memory_compare.HumanReadableBytes("2048MiB"),
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
                memory_compare.HumanReadableBytes("4096MiB"),
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

    @patch("memory_compare.open")
    def test_kexec_crash_size_returns_zero_when_crash_is_not_loaded(
        self, mock_builtin_open
    ):
        sysfs_values = {
            "/sys/kernel/kexec_crash_loaded": "0\n",
            "/sys/kernel/kexec_crash_size": "0\n",
        }
        mock_builtin_open.side_effect = lambda path, _: mock_open(
            read_data=sysfs_values[path]
        ).return_value

        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(memory_compare.get_kexec_crash_size(), 0)

        mock_builtin_open.assert_called_once_with(
            "/sys/kernel/kexec_crash_loaded", "r"
        )
        self.assertIn("No kexec crash kernel loaded", stdout.getvalue())

    @patch("memory_compare.open")
    def test_kexec_crash_size_returns_size_when_crash_is_loaded(
        self, mock_builtin_open
    ):
        sysfs_values = {
            "/sys/kernel/kexec_crash_loaded": "1\n",
            "/sys/kernel/kexec_crash_size": "2097152\n",
        }
        mock_builtin_open.side_effect = lambda path, _: mock_open(
            read_data=sysfs_values[path]
        ).return_value

        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(memory_compare.get_kexec_crash_size(), 2097152)

        self.assertEqual(
            mock_builtin_open.call_args_list,
            [
                call("/sys/kernel/kexec_crash_loaded", "r"),
                call("/sys/kernel/kexec_crash_size", "r"),
            ],
        )
        self.assertIn("Detected kexec crash size: 2MiB", stdout.getvalue())

    @patch("memory_compare.open")
    def test_kexec_crash_size_returns_zero_when_sysfs_unavailable(
        self, mock_open
    ):
        mock_open.side_effect = FileNotFoundError

        self.assertEqual(memory_compare.get_kexec_crash_size(), 0)


if __name__ == "__main__":
    unittest.main()
