#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Shane McKee <shane.mckee@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import unittest
from unittest.mock import MagicMock, patch

import lz_host


class TestCmdResource(unittest.TestCase):
    @patch("lz_host.check_host_level_zero_gpu", return_value=True)
    @patch("lz_host.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("builtins.print")
    def test_returns_0_and_prints_record_when_gpu_found(
        self, mock_print, _arch, _check
    ):
        self.assertEqual(lz_host.cmd_resource(), 0)
        mock_print.assert_called_once_with("gpu_available: True")

    @patch("lz_host.check_host_level_zero_gpu", return_value=False)
    @patch("lz_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_no_gpu(self, _arch, _check):
        self.assertEqual(lz_host.cmd_resource(), 1)


class TestCmdValidateInstall(unittest.TestCase):
    @patch("os.path.isfile", return_value=True)
    @patch("lz_host.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("builtins.print")
    def test_returns_0_and_prints_record_when_loader_found(
        self, mock_print, _arch, _isfile
    ):
        self.assertEqual(lz_host.cmd_validate_install(), 0)
        mock_print.assert_called_once_with("ze_loader_available: True")

    @patch("os.path.isfile", return_value=False)
    @patch("lz_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_loader_not_found(self, _arch, _isfile):
        self.assertEqual(lz_host.cmd_validate_install(), 1)

    @patch("os.path.isfile", return_value=True)
    @patch("lz_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_checks_correct_path(self, _arch, mock_isfile):
        lz_host.cmd_validate_install()
        mock_isfile.assert_called_once_with(
            "/usr/lib/x86_64-linux-gnu/libze_loader.so.1"
        )


class TestCmdRunTest(unittest.TestCase):
    SNAP = "/snap/level-zero-tests/current"

    @patch("subprocess.run")
    def test_passes_test_args_to_snap_binary(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        lz_host.cmd_run_test(["perf/test_perf"])
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], f"{self.SNAP}/test")
        self.assertIn("--no-confinement", cmd)
        self.assertIn("perf/test_perf", cmd)

    @patch("subprocess.run")
    def test_passes_multiple_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        lz_host.cmd_run_test(["perf/test_perf", "--gtest_filter=*", "5"])
        cmd = mock_run.call_args[0][0]
        self.assertIn("perf/test_perf", cmd)
        self.assertIn("--gtest_filter=*", cmd)
        self.assertIn("5", cmd)

    @patch("subprocess.run")
    def test_sets_snap_env(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        lz_host.cmd_run_test(["perf/test_perf"])
        env = mock_run.call_args[1]["env"]
        self.assertEqual(env["SNAP"], self.SNAP)

    @patch("subprocess.run")
    def test_returns_subprocess_returncode(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertEqual(lz_host.cmd_run_test(["perf/test_perf"]), 1)


class TestMain(unittest.TestCase):
    @patch("lz_host.cmd_resource", return_value=0)
    def test_dispatches_resource(self, mock_cmd):
        with patch("sys.argv", ["lz_host.py", "resource"]):
            self.assertEqual(lz_host.main(), 0)
        self.assertEqual(mock_cmd.call_count, 1)

    @patch("lz_host.cmd_validate_install", return_value=0)
    def test_dispatches_validate_install(self, mock_cmd):
        with patch("sys.argv", ["lz_host.py", "validate-install"]):
            self.assertEqual(lz_host.main(), 0)
        self.assertEqual(mock_cmd.call_count, 1)

    @patch("lz_host.cmd_run_test", return_value=0)
    def test_dispatches_run_test_with_args(self, mock_cmd):
        with patch("sys.argv", ["lz_host.py", "run-test", "perf/test_perf"]):
            self.assertEqual(lz_host.main(), 0)
        mock_cmd.assert_called_once_with(["perf/test_perf"])

    def test_returns_1_with_no_args(self):
        with patch("sys.argv", ["lz_host.py"]):
            self.assertEqual(lz_host.main(), 1)

    def test_returns_1_with_unknown_command(self):
        with patch("sys.argv", ["lz_host.py", "unknown-cmd"]):
            self.assertEqual(lz_host.main(), 1)

    @patch(
        "lz_host.cmd_resource",
        side_effect=RuntimeError("unexpected failure"),
    )
    def test_catches_runtime_error(self, _cmd):
        with patch("sys.argv", ["lz_host.py", "resource"]):
            self.assertEqual(lz_host.main(), 1)


if __name__ == "__main__":
    unittest.main()
