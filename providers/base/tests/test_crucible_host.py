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

import io
import json
import subprocess
import unittest
from unittest.mock import MagicMock, mock_open, patch

import crucible_host


class TestCheckHostGpu(unittest.TestCase):
    PLZ_RUN = "/snap/checkbox22/current/bin/plz-run"
    ARCH_TRIPLE = "x86_64-linux-gnu"

    @patch("subprocess.check_output")
    def test_returns_true_when_gpu_found(self, mock_check_output):
        mock_check_output.return_value = (
            "deviceType = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
        )
        self.assertTrue(
            crucible_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch("subprocess.check_output")
    def test_returns_false_when_no_gpu(self, mock_check_output):
        mock_check_output.return_value = (
            "deviceType = PHYSICAL_DEVICE_TYPE_CPU\n"
        )
        self.assertFalse(
            crucible_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "plz-run"),
    )
    def test_returns_false_on_called_process_error(self, _mock):
        self.assertFalse(
            crucible_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch("subprocess.check_output", return_value="")
    def test_passes_correct_args(self, mock_check_output):
        crucible_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        self.assertEqual(
            mock_check_output.call_args[0][0],
            [
                self.PLZ_RUN,
                "-u",
                "root",
                "-g",
                "root",
                "-E",
                "LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/lib",
                "--",
                "/usr/bin/vulkaninfo",
                "--summary",
            ],
        )


class TestCmdResource(unittest.TestCase):
    @patch("crucible_host.find_plz_run", return_value=None)
    @patch("crucible_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_1_when_plz_run_not_found(self, _arch, _plz):
        self.assertEqual(crucible_host.cmd_resource(), 1)


class TestCmdValidateInstall(unittest.TestCase):
    @patch("os.path.isfile", return_value=True)
    @patch("crucible_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_checks_correct_path(self, _arch, mock_isfile):
        crucible_host.cmd_validate_install()
        mock_isfile.assert_called_once_with(
            "/usr/lib/x86_64-linux-gnu/libvulkan.so.1"
        )



class TestFindHostIcdFilenames(unittest.TestCase):
    ICD_DIR = "/usr/share/vulkan/icd.d"

    def _icd_open(self, icd_map):
        """Return a side_effect for open() that serves fake ICD JSON by filename."""
        def _open(path, *args, **kwargs):
            name = path.split("/")[-1]
            if name in icd_map:
                return io.StringIO(json.dumps(
                    {"ICD": {"library_path": icd_map[name], "api_version": "1.3"}}
                ))
            raise OSError("not found: {}".format(path))
        return _open

    def test_excludes_virtual_icds(self):
        files = ["intel_icd.json", "gfxstream_vk_icd.json", "virtio_icd.json"]
        libs = {
            "intel_icd.json": "libvulkan_intel.so",
            "gfxstream_vk_icd.json": "libvulkan_gfxstream.so",
            "virtio_icd.json": "libvulkan_virtio.so",
        }
        with patch("os.listdir", return_value=files), \
             patch("builtins.open", side_effect=self._icd_open(libs)):
            result = crucible_host.find_host_icd_filenames()
        self.assertIn("{}/intel_icd.json".format(self.ICD_DIR), result)
        self.assertNotIn("gfxstream", result)
        self.assertNotIn("virtio", result)

    def test_returns_empty_string_when_dir_missing(self):
        with patch("os.listdir", side_effect=OSError):
            self.assertEqual(crucible_host.find_host_icd_filenames(), "")

    def test_includes_file_on_parse_error(self):
        with patch("os.listdir", return_value=["bad.json"]), \
             patch("builtins.open", side_effect=OSError):
            result = crucible_host.find_host_icd_filenames()
            self.assertIn("bad.json", result)

    def test_filters_by_vendor_prefix(self):
        files = ["intel_icd.json", "radeon_icd.json"]
        libs = {
            "intel_icd.json": "libvulkan_intel.so",
            "radeon_icd.json": "libvulkan_radeon.so",
        }
        with patch("os.listdir", return_value=files), \
             patch("builtins.open", side_effect=self._icd_open(libs)):
            result = crucible_host.find_host_icd_filenames(("intel",))
        self.assertIn("intel_icd.json", result)
        self.assertNotIn("radeon_icd.json", result)


class TestVendorPrefixesFromVulkaninfo(unittest.TestCase):
    def test_returns_prefixes_for_known_vendor(self):
        output = "    vendorID           = 0x8086\n"
        self.assertEqual(
            crucible_host._vendor_prefixes_from_vulkaninfo(output), ("intel",)
        )

    def test_returns_none_for_unknown_vendor(self):
        output = "    vendorID           = 0x1234\n"
        self.assertIsNone(crucible_host._vendor_prefixes_from_vulkaninfo(output))

    def test_returns_none_when_no_vendorid_line(self):
        output = "deviceType = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
        self.assertIsNone(crucible_host._vendor_prefixes_from_vulkaninfo(output))


class TestActiveVendorPrefixes(unittest.TestCase):
    @patch("crucible_host.prime_selected_vendor", return_value="intel")
    def test_returns_prime_vendor(self, _prime):
        self.assertEqual(crucible_host._active_vendor_prefixes(), ("intel",))

    @patch("crucible_host.prime_selected_vendor", return_value=None)
    @patch("crucible_host.find_plz_run", return_value="/usr/bin/plz-run")
    @patch("crucible_host.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("crucible_host._run_vulkaninfo", return_value="vendorID = 0x8086\n")
    def test_returns_vulkaninfo_vendor(self, _vkinfo, _arch, _plz, _prime):
        self.assertEqual(crucible_host._active_vendor_prefixes(), ("intel",))

    @patch("crucible_host.prime_selected_vendor", return_value=None)
    @patch("crucible_host.find_plz_run", return_value=None)
    @patch("crucible_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_falls_back_to_sysfs(self, _arch, _plz, _prime):
        with patch("os.listdir", return_value=["card1"]), \
             patch("builtins.open", mock_open(read_data="0x8086\n")):
            self.assertEqual(crucible_host._active_vendor_prefixes(), ("intel",))

    @patch("crucible_host.prime_selected_vendor", return_value=None)
    @patch("crucible_host.find_plz_run", return_value=None)
    @patch("crucible_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_none_when_all_methods_fail(self, _arch, _plz, _prime):
        with patch("os.listdir", side_effect=OSError):
            self.assertIsNone(crucible_host._active_vendor_prefixes())


class TestCmdRunTest(unittest.TestCase):
    SNAP = "/snap/crucible/current"
    ICD = "/usr/share/vulkan/icd.d/intel_icd.json"
    FILTER_PATTERN = "func.depthstencil.*"

    def _mock_run(self, returncode=0):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        return MagicMock(return_value=mock_result)

    @patch("crucible_host._active_vendor_prefixes", return_value=None)
    @patch("crucible_host.find_host_icd_filenames", return_value=ICD)
    def test_forwards_nonzero_returncode(self, _icd, _prefixes):
        mock_run = self._mock_run(returncode=1)
        with patch("subprocess.run", mock_run):
            self.assertEqual(crucible_host.cmd_run_test([self.FILTER_PATTERN]), 1)

    @patch("crucible_host._active_vendor_prefixes", return_value=None)
    @patch("crucible_host.find_host_icd_filenames", return_value=ICD)
    def test_passes_correct_args(self, _icd, _prefixes):
        mock_run = self._mock_run()
        with patch("subprocess.run", mock_run):
            crucible_host.cmd_run_test([self.FILTER_PATTERN])
        self.assertEqual(
            mock_run.call_args[0][0],
            [
                "{}/test".format(self.SNAP),
                "--no-confinement",
                "--no-fork",
                self.FILTER_PATTERN,
            ],
        )
        env = mock_run.call_args[1]["env"]
        self.assertEqual(env["VK_ICD_FILENAMES"], self.ICD)
        self.assertEqual(env["SNAP"], self.SNAP)
        self.assertEqual(env["NODEVICE_SELECT"], "1")

    @patch("crucible_host._active_vendor_prefixes", return_value=None)
    @patch("crucible_host.find_host_icd_filenames", return_value="")
    def test_does_not_set_vk_icd_when_none_found(self, _icd, _prefixes):
        mock_run = self._mock_run()
        with patch("subprocess.run", mock_run):
            crucible_host.cmd_run_test([self.FILTER_PATTERN])
        self.assertNotIn("VK_ICD_FILENAMES", mock_run.call_args[1]["env"])

    @patch("crucible_host._active_vendor_prefixes", return_value=None)
    @patch("crucible_host.find_host_icd_filenames", return_value=ICD)
    def test_respects_explicit_vk_icd_filenames(self, _icd, _prefixes):
        explicit = "/usr/share/vulkan/icd.d/nvidia_icd.json"
        mock_run = self._mock_run()
        with patch("subprocess.run", mock_run), \
             patch.dict("os.environ", {"VK_ICD_FILENAMES": explicit}):
            crucible_host.cmd_run_test([self.FILTER_PATTERN])
        self.assertEqual(mock_run.call_args[1]["env"]["VK_ICD_FILENAMES"], explicit)


class TestPrimeSelectedVendor(unittest.TestCase):
    @patch(
        "subprocess.check_output",
        return_value="intel\n",
    )
    def test_returns_intel(self, _mock):
        self.assertEqual(crucible_host.prime_selected_vendor(), "intel")

    @patch("subprocess.check_output", return_value="on-demand\n")
    def test_returns_none_for_on_demand(self, _mock):
        self.assertIsNone(crucible_host.prime_selected_vendor())

    @patch(
        "subprocess.check_output",
        side_effect=FileNotFoundError,
    )
    def test_returns_none_when_prime_select_not_found(self, _mock):
        self.assertIsNone(crucible_host.prime_selected_vendor())

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "prime-select"),
    )
    def test_returns_none_on_error(self, _mock):
        self.assertIsNone(crucible_host.prime_selected_vendor())



class TestMain(unittest.TestCase):
    @patch("crucible_host.cmd_run_test", return_value=0)
    def test_dispatches_run_test_with_args(self, mock_cmd):
        with patch(
            "sys.argv",
            ["crucible_host.py", "run-test", "--fork", "func.depthstencil.*"],
        ):
            self.assertEqual(crucible_host.main(), 0)
        mock_cmd.assert_called_once_with(
            ["--fork", "func.depthstencil.*"]
        )

    def test_returns_1_with_no_args(self):
        with patch("sys.argv", ["crucible_host.py"]):
            self.assertEqual(crucible_host.main(), 1)

    @patch(
        "crucible_host.cmd_resource",
        side_effect=RuntimeError("could not determine multiarch triple"),
    )
    def test_returns_1_on_runtime_error(self, _cmd):
        with patch("sys.argv", ["crucible_host.py", "resource"]):
            self.assertEqual(crucible_host.main(), 1)


if __name__ == "__main__":
    unittest.main()
