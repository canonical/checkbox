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
from unittest.mock import mock_open, patch

import host_utils


class TestGetArchTriple(unittest.TestCase):
    @patch("sysconfig.get_config_var", return_value="x86_64-linux-gnu")
    def test_returns_multiarch_value(self, _cfg):
        self.assertEqual(host_utils.get_arch_triple(), "x86_64-linux-gnu")

    @patch("sysconfig.get_config_var", return_value=None)
    def test_raises_when_multiarch_is_none(self, _cfg):
        with self.assertRaises(RuntimeError):
            host_utils.get_arch_triple()


class TestCheckHostGpu(unittest.TestCase):
    PLZ_RUN = "/snap/checkbox22/current/bin/plz-run"
    ARCH_TRIPLE = "x86_64-linux-gnu"

    VULKANINFO_GPU_OUTPUT = (
        "WARNING: [Loader Message] Code 0 : ICD for selected physical device"
        " does not export"
        " vkGetPhysicalDeviceDisplayPlanePropertiesKHR!\n"
        "WARNING: [Loader Message] Code 0 : ICD for selected physical device"
        " does not export"
        " vkGetPhysicalDeviceDisplayPropertiesKHR!\n"
        "==========\n"
        "VULKANINFO\n"
        "==========\n"
        "\n"
        "Vulkan Instance Version: 1.4.341\n"
        "\n"
        "\n"
        "Instance Extensions: count = 26\n"
        "-------------------------------\n"
        "VK_EXT_acquire_drm_display             : extension revision 1\n"
        "VK_EXT_debug_utils                     : extension revision 2\n"
        "VK_KHR_surface                         : extension revision 25\n"
        "\n"
        "Instance Layers: count = 9\n"
        "--------------------------\n"
        "VK_LAYER_MESA_device_select       Linux device selection layer"
        "                                 1.4.303  version 1\n"
        "VK_LAYER_MESA_overlay             Mesa Overlay layer"
        "                                           1.4.303  version 1\n"
        "\n"
        "Devices:\n"
        "========\n"
        "GPU0:\n"
        "    apiVersion         = 1.4.335\n"
        "    driverVersion      = 26.0.2\n"
        "    vendorID           = 0x8086\n"
        "    deviceID           = 0x7dd1\n"
        "    deviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
        "    deviceName         = Intel(R) Graphics (ARL)\n"
        "    driverID           = DRIVER_ID_INTEL_OPEN_SOURCE_MESA\n"
        "    driverName         = Intel open-source Mesa driver\n"
        "    driverInfo         = Mesa 26.0.2-1ubuntu1\n"
        "GPU1:\n"
        "    apiVersion         = 1.4.335\n"
        "    driverVersion      = 26.0.2\n"
        "    vendorID           = 0x10005\n"
        "    deviceID           = 0x0000\n"
        "    deviceType         = PHYSICAL_DEVICE_TYPE_CPU\n"
        "    deviceName         = llvmpipe (LLVM 21.1.8, 256 bits)\n"
        "    driverID           = DRIVER_ID_MESA_LLVMPIPE\n"
        "    driverName         = llvmpipe\n"
        "    driverInfo         = Mesa 26.0.2-1ubuntu1 (LLVM 21.1.8)\n"
    )

    VULKANINFO_NO_GPU_OUTPUT = (
        "'DISPLAY' environment variable not set... skipping surface info\n"
        "==========\n"
        "VULKANINFO\n"
        "==========\n"
        "\n"
        "Vulkan Instance Version: 1.3.275\n"
        "\n"
        "\n"
        "Instance Extensions: count = 24\n"
        "-------------------------------\n"
        "VK_EXT_acquire_drm_display             : extension revision 1\n"
        "VK_KHR_surface                         : extension revision 25\n"
        "\n"
        "Instance Layers: count = 3\n"
        "--------------------------\n"
        "VK_LAYER_MESA_device_select Linux device selection layer"
        " 1.4.303  version 1\n"
        "\n"
        "Devices:\n"
        "========\n"
        "GPU0:\n"
        "    apiVersion         = 1.4.318\n"
        "    driverVersion      = 25.2.8\n"
        "    vendorID           = 0x10005\n"
        "    deviceID           = 0x0000\n"
        "    deviceType         = PHYSICAL_DEVICE_TYPE_CPU\n"
        "    deviceName         = llvmpipe (LLVM 20.1.2, 256 bits)\n"
        "    driverID           = DRIVER_ID_MESA_LLVMPIPE\n"
        "    driverName         = llvmpipe\n"
        "    driverInfo         = Mesa 25.2.8-0ubuntu0.24.04.1 (LLVM 20.1.2)\n"
    )

    @patch("subprocess.check_output")
    def test_returns_true_when_gpu_found(self, mock_check_output):
        mock_check_output.return_value = self.VULKANINFO_GPU_OUTPUT
        self.assertTrue(host_utils.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE))

    @patch("subprocess.check_output")
    def test_returns_false_when_no_gpu(self, mock_check_output):
        mock_check_output.return_value = self.VULKANINFO_NO_GPU_OUTPUT
        self.assertFalse(host_utils.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE))

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "plz-run"),
    )
    def test_returns_false_on_called_process_error(self, _mock):
        self.assertFalse(host_utils.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE))

    @patch("subprocess.check_output", return_value="")
    def test_passes_correct_args(self, mock_check_output):
        host_utils.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        self.assertEqual(
            mock_check_output.call_args[0][0],
            [
                self.PLZ_RUN,
                "-u", "root",
                "-g", "root",
                "-E",
                "LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/lib",
                "--",
                "/usr/bin/vulkaninfo",
                "--summary",
            ],
        )


class TestPrimeSelectedVendor(unittest.TestCase):
    @patch("subprocess.check_output", return_value="intel\n")
    def test_returns_known_vendor(self, _mock):
        self.assertEqual(host_utils.prime_selected_vendor(), "intel")

    @patch("subprocess.check_output", return_value="on-demand\n")
    def test_returns_none_for_on_demand(self, _mock):
        self.assertIsNone(host_utils.prime_selected_vendor())

    @patch("subprocess.check_output", side_effect=FileNotFoundError)
    def test_returns_none_when_prime_select_not_found(self, _mock):
        self.assertIsNone(host_utils.prime_selected_vendor())

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "prime-select"),
    )
    def test_returns_none_on_error(self, _mock):
        self.assertIsNone(host_utils.prime_selected_vendor())


class TestVendorPrefixesFromVulkaninfo(unittest.TestCase):
    def test_returns_prefixes_for_known_vendor(self):
        output = "    vendorID           = 0x8086\n"
        self.assertEqual(
            host_utils._vendor_prefixes_from_vulkaninfo(output), ("intel",)
        )

    def test_returns_none_for_unknown_vendor(self):
        output = "    vendorID           = 0x1234\n"
        self.assertIsNone(host_utils._vendor_prefixes_from_vulkaninfo(output))

    def test_returns_none_when_no_vendorid_line(self):
        output = "deviceType = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
        self.assertIsNone(host_utils._vendor_prefixes_from_vulkaninfo(output))


class TestActiveVendorPrefixes(unittest.TestCase):
    @patch("host_utils.prime_selected_vendor", return_value="intel")
    def test_returns_prime_vendor(self, _prime):
        self.assertEqual(host_utils._active_vendor_prefixes(), ("intel",))

    @patch("host_utils.prime_selected_vendor", return_value=None)
    @patch("host_utils.find_plz_run", return_value="/usr/bin/plz-run")
    @patch("host_utils.get_arch_triple", return_value="x86_64-linux-gnu")
    @patch("host_utils._run_vulkaninfo", return_value="vendorID = 0x8086\n")
    def test_returns_vulkaninfo_vendor(self, _vkinfo, _arch, _plz, _prime):
        self.assertEqual(host_utils._active_vendor_prefixes(), ("intel",))

    @patch("host_utils.prime_selected_vendor", return_value=None)
    @patch("host_utils.find_plz_run", return_value=None)
    @patch("host_utils.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_falls_back_to_sysfs(self, _arch, _plz, _prime):
        with patch("os.listdir", return_value=["card1"]), \
             patch("builtins.open", mock_open(read_data="0x8086\n")):
            self.assertEqual(host_utils._active_vendor_prefixes(), ("intel",))

    @patch("host_utils.prime_selected_vendor", return_value=None)
    @patch("host_utils.find_plz_run", return_value=None)
    @patch("host_utils.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_none_when_all_methods_fail(self, _arch, _plz, _prime):
        with patch("os.listdir", side_effect=OSError):
            self.assertIsNone(host_utils._active_vendor_prefixes())


class TestFindHostIcdFilenames(unittest.TestCase):
    ICD_DIR = "/usr/share/vulkan/icd.d"

    def _icd_open(self, icd_map):
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
            result = host_utils.find_host_icd_filenames()
        self.assertIn("{}/intel_icd.json".format(self.ICD_DIR), result)
        self.assertNotIn("gfxstream", result)
        self.assertNotIn("virtio", result)

    def test_filters_by_vendor_prefix(self):
        files = ["intel_icd.json", "radeon_icd.json"]
        libs = {
            "intel_icd.json": "libvulkan_intel.so",
            "radeon_icd.json": "libvulkan_radeon.so",
        }
        with patch("os.listdir", return_value=files), \
             patch("builtins.open", side_effect=self._icd_open(libs)):
            result = host_utils.find_host_icd_filenames(("intel",))
        self.assertIn("intel_icd.json", result)
        self.assertNotIn("radeon_icd.json", result)

    def test_returns_empty_string_when_dir_missing(self):
        with patch("os.listdir", side_effect=OSError):
            self.assertEqual(host_utils.find_host_icd_filenames(), "")

    def test_includes_file_on_parse_error(self):
        with patch("os.listdir", return_value=["bad.json"]), \
             patch("builtins.open", side_effect=OSError):
            self.assertIn("bad.json", host_utils.find_host_icd_filenames())


if __name__ == "__main__":
    unittest.main()
