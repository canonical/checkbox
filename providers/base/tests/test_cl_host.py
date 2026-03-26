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

import subprocess
import unittest
from unittest.mock import MagicMock, patch

import cl_host


class TestGetArchTriple(unittest.TestCase):
    @patch("sysconfig.get_config_var", return_value="x86_64-linux-gnu")
    def test_returns_multiarch_from_sysconfig(self, mock_gcv):
        self.assertEqual(cl_host.get_arch_triple(), "x86_64-linux-gnu")
        mock_gcv.assert_called_once_with("MULTIARCH")


class TestFindPlzRun(unittest.TestCase):
    @patch("shutil.which", return_value="/snap/checkbox22/current/bin/plz-run")
    def test_returns_path_when_found(self, mock_which):
        self.assertEqual(
            cl_host.find_plz_run(),
            "/snap/checkbox22/current/bin/plz-run",
        )
        mock_which.assert_called_once_with("plz-run")

    @patch("shutil.which", return_value=None)
    def test_returns_none_when_not_found(self, mock_which):
        self.assertIsNone(cl_host.find_plz_run())


class TestCheckHostGpu(unittest.TestCase):
    PLZ_RUN = "/snap/checkbox22/current/bin/plz-run"
    ARCH_TRIPLE = "x86_64-linux-gnu"

    CLINFO_GPU_OUTPUT = "[INTEL/0]    CL_DEVICE_TYPE                                  CL_DEVICE_TYPE_GPU\n"

    CLINFO_NO_GPU_OUTPUT = ""

    @patch("os.path.isfile", return_value=False)
    def test_returns_false_when_clinfo_missing(self, _isfile):
        self.assertFalse(
            cl_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch("subprocess.check_output")
    def test_returns_true_when_gpu_found(self, mock_check_output):
        mock_check_output.return_value = self.CLINFO_GPU_OUTPUT
        self.assertTrue(cl_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE))

    @patch("subprocess.check_output")
    def test_returns_false_when_no_gpu(self, mock_check_output):
        mock_check_output.return_value = self.CLINFO_NO_GPU_OUTPUT
        self.assertFalse(
            cl_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "plz-run"),
    )
    def test_returns_false_on_called_process_error(self, mock_check_output):
        self.assertFalse(
            cl_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch("subprocess.check_output", return_value="")
    def test_passes_correct_args(self, mock_check_output):
        cl_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        cmd = mock_check_output.call_args[0][0]
        self.assertIn(
            "LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/lib", cmd
        )
        self.assertIn("/usr/bin/clinfo", cmd)
        self.assertIn("--prop", cmd)
        self.assertIn("CL_DEVICE_TYPE", cmd)


class TestCmdResource(unittest.TestCase):
    @patch("cl_host.check_host_gpu", return_value=True)
    @patch(
        "cl_host.find_plz_run",
        return_value="/snap/checkbox22/current/bin/plz-run",
    )
    @patch("cl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("builtins.print")
    def test_returns_0_and_prints_record_when_gpu_found(
        self, mock_print, _arch, _plz, _check
    ):
        self.assertEqual(cl_host.cmd_resource(), 0)
        mock_print.assert_called_once_with("gpu_available: True")

    @patch("cl_host.check_host_gpu", return_value=False)
    @patch(
        "cl_host.find_plz_run",
        return_value="/snap/checkbox22/current/bin/plz-run",
    )
    @patch("cl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_no_gpu(self, _arch, _plz, _check):
        self.assertEqual(cl_host.cmd_resource(), 1)

    @patch("cl_host.find_plz_run", return_value=None)
    @patch("cl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_plz_run_not_found(self, _arch, _plz):
        self.assertEqual(cl_host.cmd_resource(), 1)


class TestCmdValidateInstall(unittest.TestCase):
    @patch("os.path.isfile", return_value=True)
    @patch("cl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("builtins.print")
    def test_returns_0_and_prints_record_when_ocl_found(
        self, mock_print, _arch, _isfile
    ):
        self.assertEqual(cl_host.cmd_validate_install(), 0)
        mock_print.assert_called_once_with("ocl_icd_available: True")

    @patch("os.path.isfile", return_value=False)
    @patch("cl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_ocl_not_found(self, _arch, _isfile):
        self.assertEqual(cl_host.cmd_validate_install(), 1)

    @patch("os.path.isfile", return_value=True)
    @patch("cl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_checks_correct_path(self, _arch, mock_isfile):
        cl_host.cmd_validate_install()
        mock_isfile.assert_called_once_with(
            "/usr/lib/x86_64-linux-gnu/libOpenCL.so.1"
        )


class TestCmdRunTest(unittest.TestCase):
    SNAP = "/snap/opencl-cts/current"

    @patch("subprocess.run")
    def test_passes_test_args_to_snap_binary(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        cl_host.cmd_run_test(["basic/test_basic"])
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "{}/test".format(self.SNAP))
        self.assertIn("--no-confinement", cmd)
        self.assertIn("basic/test_basic", cmd)

    @patch("subprocess.run")
    def test_passes_multiple_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        cl_host.cmd_run_test(
            ["allocations/test_allocations", "single", "5", "all"]
        )
        cmd = mock_run.call_args[0][0]
        self.assertIn("allocations/test_allocations", cmd)
        self.assertIn("single", cmd)
        self.assertIn("5", cmd)
        self.assertIn("all", cmd)

    @patch("subprocess.run")
    def test_sets_snap_env(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        cl_host.cmd_run_test(["basic/test_basic"])
        env = mock_run.call_args[1]["env"]
        self.assertEqual(env["SNAP"], self.SNAP)

    @patch("subprocess.run")
    def test_returns_subprocess_returncode(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertEqual(cl_host.cmd_run_test(["basic/test_basic"]), 1)


if __name__ == "__main__":
    unittest.main()
