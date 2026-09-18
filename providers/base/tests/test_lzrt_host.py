#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

import lzrt_host


class TestCmdResource(unittest.TestCase):
    @patch("lzrt_host.has_intel_gpu", return_value=True)
    @patch("builtins.print")
    def test_returns_0_and_prints_record_when_intel_gpu(
        self, mock_print, _has
    ):
        self.assertEqual(lzrt_host.cmd_resource(), 0)
        mock_print.assert_called_once_with("gpu_available: True")

    @patch("lzrt_host.has_intel_gpu", return_value=False)
    def test_returns_1_when_no_intel_gpu(self, _has):
        self.assertEqual(lzrt_host.cmd_resource(), 1)


class TestCmdValidateInstall(unittest.TestCase):
    @patch("os.path.isfile", return_value=True)
    @patch("lzrt_host.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("builtins.print")
    def test_returns_0_and_prints_record_when_loader_found(
        self, mock_print, _arch, _isfile
    ):
        self.assertEqual(lzrt_host.cmd_validate_install(), 0)
        mock_print.assert_called_once_with("ze_loader_available: True")

    @patch("os.path.isfile", return_value=False)
    @patch("lzrt_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_loader_not_found(self, _arch, _isfile):
        self.assertEqual(lzrt_host.cmd_validate_install(), 1)


class TestCmdRunTest(unittest.TestCase):
    SNAP = "/snap/level-zero-raytracing-tests/current"

    @patch("subprocess.run")
    def test_passes_test_args_to_snap_binary(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        lzrt_host.cmd_run_test(["embree_rthwif_cornell_box"])
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "{}/test".format(self.SNAP))
        self.assertIn("--no-confinement", cmd)
        self.assertIn("embree_rthwif_cornell_box", cmd)
        env = mock_run.call_args[1]["env"]
        self.assertEqual(env["SNAP"], self.SNAP)


class TestMain(unittest.TestCase):
    @patch("lzrt_host.cmd_resource", return_value=0)
    def test_dispatches_resource(self, mock_cmd):
        with patch("sys.argv", ["lzrt_host.py", "resource"]):
            self.assertEqual(lzrt_host.main(), 0)
        self.assertEqual(mock_cmd.call_count, 1)

    @patch("lzrt_host.cmd_validate_install", return_value=0)
    def test_dispatches_validate_install(self, mock_cmd):
        with patch("sys.argv", ["lzrt_host.py", "validate-install"]):
            self.assertEqual(lzrt_host.main(), 0)
        self.assertEqual(mock_cmd.call_count, 1)

    @patch("lzrt_host.cmd_run_test", return_value=0)
    def test_dispatches_run_test_with_args(self, mock_cmd):
        with patch(
            "sys.argv",
            ["lzrt_host.py", "run-test", "embree_rthwif_cornell_box"],
        ):
            self.assertEqual(lzrt_host.main(), 0)
        mock_cmd.assert_called_once_with(["embree_rthwif_cornell_box"])

    @patch("sys.argv", ["lzrt_host.py"])
    def test_missing_command_returns_error(self):
        self.assertEqual(lzrt_host.main(), 1)

    @patch("sys.argv", ["lzrt_host.py", "bogus"])
    def test_unknown_command_returns_error(self):
        self.assertEqual(lzrt_host.main(), 1)

    @patch(
        "lzrt_host.cmd_resource",
        side_effect=RuntimeError("unexpected failure"),
    )
    def test_catches_runtime_error(self, _cmd):
        with patch("sys.argv", ["lzrt_host.py", "resource"]):
            self.assertEqual(lzrt_host.main(), 1)


if __name__ == "__main__":
    unittest.main()
