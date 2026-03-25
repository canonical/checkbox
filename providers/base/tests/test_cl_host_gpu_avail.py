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
from unittest.mock import MagicMock, mock_open, patch

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
    TMPFILE = "/var/tmp/tmpABCDEF"

    def _make_tmpfile_mock(self):
        """Return a mock that behaves like NamedTemporaryFile(delete=False)."""
        tmp = MagicMock()
        tmp.name = self.TMPFILE  # .name must be set as an attribute, not via
        # the MagicMock(name=...) constructor which sets the mock's own name
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=tmp)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    @patch("os.unlink")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_returns_true_when_gpu_found(
        self, mock_ntf, mock_run, mock_unlink
    ):
        mock_ntf.return_value = self._make_tmpfile_mock()
        with patch(
            "builtins.open", mock_open(read_data="CL_DEVICE_TYPE_GPU\n")
        ):
            result = cl_host_gpu_avail.check_host_gpu(
                self.PLZ_RUN, self.ARCH_TRIPLE
            )
        self.assertTrue(result)
        mock_unlink.assert_called_once_with(self.TMPFILE)

    @patch("os.unlink")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_returns_false_when_no_gpu(self, mock_ntf, mock_run, mock_unlink):
        mock_ntf.return_value = self._make_tmpfile_mock()
        with patch(
            "builtins.open", mock_open(read_data="Number of platforms: 0\n")
        ):
            result = cl_host_gpu_avail.check_host_gpu(
                self.PLZ_RUN, self.ARCH_TRIPLE
            )
        self.assertFalse(result)

    @patch("os.unlink")
    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_passes_correct_ld_library_path(
        self, mock_ntf, mock_run, mock_unlink
    ):
        mock_ntf.return_value = self._make_tmpfile_mock()
        with patch("builtins.open", mock_open(read_data="")):
            cl_host_gpu_avail.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        cmd = mock_run.call_args[0][0]
        bash_cmd = cmd[-1]
        self.assertIn("/usr/lib/x86_64-linux-gnu:/usr/lib", bash_cmd)
        self.assertIn("/usr/bin/clinfo", bash_cmd)


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
