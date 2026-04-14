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

import vk_host


class TestCmdResource(unittest.TestCase):
    @patch("vk_host.check_host_gpu", return_value=True)
    @patch("vk_host.find_plz_run", return_value="/snap/checkbox22/current/bin/plz-run")
    @patch("vk_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_0_when_gpu_found(self, _arch, _plz, _check):
        self.assertEqual(vk_host.cmd_resource(), 0)

    @patch("vk_host.check_host_gpu", return_value=False)
    @patch("vk_host.find_plz_run", return_value="/snap/checkbox22/current/bin/plz-run")
    @patch("vk_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_no_gpu(self, _arch, _plz, _check):
        self.assertEqual(vk_host.cmd_resource(), 1)

    @patch("vk_host.find_plz_run", return_value=None)
    @patch("vk_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_plz_run_not_found(self, _arch, _plz):
        self.assertEqual(vk_host.cmd_resource(), 1)


class TestCmdValidateInstall(unittest.TestCase):
    @patch("os.path.isfile", return_value=True)
    @patch("vk_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_0_when_vk_found(self, _arch, _isfile):
        self.assertEqual(vk_host.cmd_validate_install(), 0)

    @patch("os.path.isfile", return_value=False)
    @patch("vk_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_vk_not_found(self, _arch, _isfile):
        self.assertEqual(vk_host.cmd_validate_install(), 1)

    @patch("os.path.isfile", return_value=True)
    @patch("vk_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_checks_correct_path(self, _arch, mock_isfile):
        vk_host.cmd_validate_install()
        mock_isfile.assert_called_once_with(
            "/usr/lib/x86_64-linux-gnu/libvulkan.so.1"
        )


class TestCmdRunTest(unittest.TestCase):
    SNAP = "/snap/vulkan-cts/current"
    ICD = "/usr/share/vulkan/icd.d/intel_icd.json"
    CASELIST = "--caselist=mustpass/main/vk-default/api.txt"

    def _mock_run(self, returncode=0):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        return MagicMock(return_value=mock_result)

    @patch("vk_host._active_vendor_prefixes", return_value=None)
    @patch("vk_host.find_host_icd_filenames", return_value=ICD)
    def test_passes_correct_args(self, _icd, _prefixes):
        mock_run = self._mock_run()
        with patch("subprocess.run", mock_run):
            vk_host.cmd_run_test([self.CASELIST])
        self.assertEqual(
            mock_run.call_args[0][0],
            ["{}/test".format(self.SNAP), "--no-confinement", self.CASELIST],
        )
        env = mock_run.call_args[1]["env"]
        self.assertEqual(env["VK_ICD_FILENAMES"], self.ICD)
        self.assertEqual(env["SNAP"], self.SNAP)
        self.assertEqual(env["NODEVICE_SELECT"], "1")

    @patch("vk_host._active_vendor_prefixes", return_value=None)
    @patch("vk_host.find_host_icd_filenames", return_value=ICD)
    def test_forwards_nonzero_returncode(self, _icd, _prefixes):
        mock_run = self._mock_run(returncode=1)
        with patch("subprocess.run", mock_run):
            self.assertEqual(vk_host.cmd_run_test([self.CASELIST]), 1)

    @patch("vk_host._active_vendor_prefixes", return_value=None)
    @patch("vk_host.find_host_icd_filenames", return_value="")
    def test_does_not_set_vk_icd_when_none_found(self, _icd, _prefixes):
        mock_run = self._mock_run()
        with patch("subprocess.run", mock_run):
            vk_host.cmd_run_test([self.CASELIST])
        self.assertNotIn("VK_ICD_FILENAMES", mock_run.call_args[1]["env"])

    @patch("vk_host._active_vendor_prefixes", return_value=None)
    @patch("vk_host.find_host_icd_filenames", return_value=ICD)
    def test_respects_explicit_vk_icd_filenames(self, _icd, _prefixes):
        explicit = "/usr/share/vulkan/icd.d/nvidia_icd.json"
        mock_run = self._mock_run()
        with patch("subprocess.run", mock_run), \
             patch.dict("os.environ", {"VK_ICD_FILENAMES": explicit}):
            vk_host.cmd_run_test([self.CASELIST])
        self.assertEqual(mock_run.call_args[1]["env"]["VK_ICD_FILENAMES"], explicit)


class TestMain(unittest.TestCase):
    @patch("vk_host.cmd_run_test", return_value=0)
    def test_dispatches_run_test_with_args(self, mock_cmd):
        with patch(
            "sys.argv",
            ["vk_host.py", "run-test", "--caselist=mustpass/main/vk-default/api.txt"],
        ):
            self.assertEqual(vk_host.main(), 0)
        mock_cmd.assert_called_once_with(
            ["--caselist=mustpass/main/vk-default/api.txt"]
        )

    def test_returns_1_with_no_args(self):
        with patch("sys.argv", ["vk_host.py"]):
            self.assertEqual(vk_host.main(), 1)

    @patch(
        "vk_host.cmd_resource",
        side_effect=RuntimeError("could not determine multiarch triple"),
    )
    def test_returns_1_on_runtime_error(self, _cmd):
        with patch("sys.argv", ["vk_host.py", "resource"]):
            self.assertEqual(vk_host.main(), 1)


if __name__ == "__main__":
    unittest.main()
