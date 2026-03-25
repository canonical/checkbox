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
from unittest.mock import patch

import cl_host_gpu_avail


class TestGetArchTriple(unittest.TestCase):
    @patch("sysconfig.get_config_var", return_value="x86_64-linux-gnu")
    def test_returns_multiarch_from_sysconfig(self, mock_gcv):
        self.assertEqual(cl_host_gpu_avail.get_arch_triple(), "x86_64-linux-gnu")
        mock_gcv.assert_called_once_with("MULTIARCH")


class TestFindPlzRun(unittest.TestCase):
    @patch("shutil.which", return_value="/snap/checkbox22/current/bin/plz-run")
    def test_returns_path_when_found(self, mock_which):
        self.assertEqual(
            cl_host_gpu_avail.find_plz_run(),
            "/snap/checkbox22/current/bin/plz-run",
        )
        mock_which.assert_called_once_with("plz-run")

    @patch("shutil.which", return_value=None)
    def test_returns_none_when_not_found(self, mock_which):
        self.assertIsNone(cl_host_gpu_avail.find_plz_run())


class TestCheckHostGpu(unittest.TestCase):
    PLZ_RUN = "/snap/checkbox22/current/bin/plz-run"
    ARCH_TRIPLE = "x86_64-linux-gnu"

    @patch("subprocess.check_output", return_value="CL_DEVICE_TYPE_GPU\n")
    def test_returns_true_when_gpu_found(self, mock_check_output):
        self.assertTrue(
            cl_host_gpu_avail.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch("subprocess.check_output", return_value="Number of platforms: 0\n")
    def test_returns_false_when_no_gpu(self, mock_check_output):
        self.assertFalse(
            cl_host_gpu_avail.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "plz-run"),
    )
    def test_returns_false_on_called_process_error(self, mock_check_output):
        self.assertFalse(
            cl_host_gpu_avail.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch("subprocess.check_output", return_value="")
    def test_passes_correct_args(self, mock_check_output):
        cl_host_gpu_avail.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        cmd = mock_check_output.call_args[0][0]
        self.assertIn("LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/lib", cmd)
        self.assertIn("/usr/bin/clinfo", cmd)


class TestMain(unittest.TestCase):
    @patch("cl_host_gpu_avail.check_host_gpu", return_value=True)
    @patch(
        "cl_host_gpu_avail.find_plz_run",
        return_value="/snap/checkbox22/current/bin/plz-run",
    )
    @patch("cl_host_gpu_avail.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("builtins.print")
    def test_returns_0_and_prints_record_when_gpu_found(
        self, mock_print, _arch, _plz, _check
    ):
        self.assertEqual(cl_host_gpu_avail.main(), 0)
        mock_print.assert_called_once_with("gpu_available: True")

    @patch("cl_host_gpu_avail.check_host_gpu", return_value=False)
    @patch(
        "cl_host_gpu_avail.find_plz_run",
        return_value="/snap/checkbox22/current/bin/plz-run",
    )
    @patch("cl_host_gpu_avail.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_no_gpu(self, _arch, _plz, _check):
        self.assertEqual(cl_host_gpu_avail.main(), 1)

    @patch("cl_host_gpu_avail.find_plz_run", return_value=None)
    @patch("cl_host_gpu_avail.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_plz_run_not_found(self, _arch, _plz):
        self.assertEqual(cl_host_gpu_avail.main(), 1)


if __name__ == "__main__":
    unittest.main()
