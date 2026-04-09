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

import vk_host


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
        "VK_EXT_acquire_xlib_display            : extension revision 1\n"
        "VK_EXT_debug_report                    : extension revision 10\n"
        "VK_EXT_debug_utils                     : extension revision 2\n"
        "VK_EXT_direct_mode_display             : extension revision 1\n"
        "VK_EXT_display_surface_counter         : extension revision 1\n"
        "VK_EXT_headless_surface                : extension revision 1\n"
        "VK_EXT_layer_settings                  : extension revision 2\n"
        "VK_EXT_surface_maintenance1            : extension revision 1\n"
        "VK_EXT_swapchain_colorspace            : extension revision 5\n"
        "VK_KHR_device_group_creation           : extension revision 1\n"
        "VK_KHR_display                         : extension revision 23\n"
        "VK_KHR_external_fence_capabilities     : extension revision 1\n"
        "VK_KHR_external_memory_capabilities    : extension revision 1\n"
        "VK_KHR_external_semaphore_capabilities : extension revision 1\n"
        "VK_KHR_get_display_properties2         : extension revision 1\n"
        "VK_KHR_get_physical_device_properties2 : extension revision 2\n"
        "VK_KHR_get_surface_capabilities2       : extension revision 1\n"
        "VK_KHR_portability_enumeration         : extension revision 1\n"
        "VK_KHR_surface                         : extension revision 25\n"
        "VK_KHR_surface_maintenance1            : extension revision 1\n"
        "VK_KHR_surface_protected_capabilities  : extension revision 1\n"
        "VK_KHR_wayland_surface                 : extension revision 6\n"
        "VK_KHR_xcb_surface                     : extension revision 6\n"
        "VK_KHR_xlib_surface                    : extension revision 6\n"
        "VK_LUNARG_direct_driver_loading        : extension revision 1\n"
        "\n"
        "Instance Layers: count = 9\n"
        "--------------------------\n"
        "VK_LAYER_INTEL_nullhw             INTEL NULL HW                  "
        "                              1.1.73   version 1\n"
        "VK_LAYER_MESA_anti_lag            Open-source "
        "implementation of the VK_AMD_anti_lag extension. 1.4.303  version 1\n"
        "VK_LAYER_MESA_device_select       Linux device selection layer"
        "                                 1.4.303  version 1\n"
        "VK_LAYER_MESA_overlay             Mesa Overlay layer"
        "                                           1.4.303  version 1\n"
        "VK_LAYER_MESA_screenshot          Mesa Screenshot layer"
        "                                        1.4.303  version 1\n"
        "VK_LAYER_VALVE_steam_fossilize_32 Steam Pipeline Caching Layer"
        "                                 1.3.207  version 1\n"
        "VK_LAYER_VALVE_steam_fossilize_64 Steam Pipeline Caching Layer"
        "                                 1.3.207  version 1\n"
        "VK_LAYER_VALVE_steam_overlay_32   Steam Overlay Layer"
        "                                          1.3.207  version 1\n"
        "VK_LAYER_VALVE_steam_overlay_64   Steam Overlay Layer"
        "                                          1.3.207  version 1\n"
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
        "    conformanceVersion = 1.4.0.0\n"
        "    deviceUUID         = 8680d17d-0300-0000-0002-000000000000\n"
        "    driverUUID         = 0deb9f3c-9818-2551-c837-38dd9378ef96\n"
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
        "    conformanceVersion = 1.3.1.1\n"
        "    deviceUUID         = 6d657361-3236-2e30-2e32-2d3175627500\n"
        "    driverUUID         = 6c6c766d-7069-7065-5555-494400000000\n"
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
        "VK_EXT_acquire_xlib_display            : extension revision 1\n"
        "VK_EXT_debug_report                    : extension revision 10\n"
        "VK_EXT_debug_utils                     : extension revision 2\n"
        "VK_EXT_direct_mode_display             : extension revision 1\n"
        "VK_EXT_display_surface_counter         : extension revision 1\n"
        "VK_EXT_headless_surface                : extension revision 1\n"
        "VK_EXT_surface_maintenance1            : extension revision 1\n"
        "VK_EXT_swapchain_colorspace            : extension revision 5\n"
        "VK_KHR_device_group_creation           : extension revision 1\n"
        "VK_KHR_display                         : extension revision 23\n"
        "VK_KHR_external_fence_capabilities     : extension revision 1\n"
        "VK_KHR_external_memory_capabilities    : extension revision 1\n"
        "VK_KHR_external_semaphore_capabilities : extension revision 1\n"
        "VK_KHR_get_display_properties2         : extension revision 1\n"
        "VK_KHR_get_physical_device_properties2 : extension revision 2\n"
        "VK_KHR_get_surface_capabilities2       : extension revision 1\n"
        "VK_KHR_portability_enumeration         : extension revision 1\n"
        "VK_KHR_surface                         : extension revision 25\n"
        "VK_KHR_surface_protected_capabilities  : extension revision 1\n"
        "VK_KHR_wayland_surface                 : extension revision 6\n"
        "VK_KHR_xcb_surface                     : extension revision 6\n"
        "VK_KHR_xlib_surface                    : extension revision 6\n"
        "VK_LUNARG_direct_driver_loading        : extension revision 1\n"
        "\n"
        "Instance Layers: count = 3\n"
        "--------------------------\n"
        "VK_LAYER_INTEL_nullhw       INTEL NULL HW"
        "                1.1.73   version 1\n"
        "VK_LAYER_MESA_device_select Linux device selection layer"
        " 1.4.303  version 1\n"
        "VK_LAYER_MESA_overlay       Mesa Overlay layer"
        "           1.4.303  version 1\n"
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
        "    conformanceVersion = 1.3.1.1\n"
        "    deviceUUID         = 6d657361-3235-2e32-2e38-2d3075627500\n"
        "    driverUUID         = 6c6c766d-7069-7065-5555-494400000000\n"
    )

    @patch("subprocess.check_output")
    def test_returns_true_when_gpu_found(self, mock_check_output):
        mock_check_output.return_value = self.VULKANINFO_GPU_OUTPUT
        self.assertTrue(vk_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE))

    @patch("subprocess.check_output")
    def test_returns_false_when_no_gpu(self, mock_check_output):
        mock_check_output.return_value = self.VULKANINFO_NO_GPU_OUTPUT
        self.assertFalse(
            vk_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "plz-run"),
    )
    def test_returns_false_on_called_process_error(self, mock_check_output):
        self.assertFalse(
            vk_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
        )

    @patch("subprocess.check_output", return_value="")
    def test_passes_correct_args(self, mock_check_output):
        vk_host.check_host_gpu(self.PLZ_RUN, self.ARCH_TRIPLE)
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
    @patch("vk_host.check_host_gpu", return_value=True)
    @patch(
        "vk_host.find_plz_run",
        return_value="/snap/checkbox22/current/bin/plz-run",
    )
    @patch("vk_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_0_when_gpu_found(self, _arch, _plz, _check):
        self.assertEqual(vk_host.cmd_resource(), 0)

    @patch("vk_host.check_host_gpu", return_value=False)
    @patch(
        "vk_host.find_plz_run",
        return_value="/snap/checkbox22/current/bin/plz-run",
    )
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

    @patch("subprocess.run")
    def test_passes_test_args_to_snap_binary(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        vk_host.cmd_run_test(["--caselist=mustpass/main/vk-default/api.txt"])
        self.assertEqual(
            mock_run.call_args[0][0],
            [
                "{}/test".format(self.SNAP),
                "--no-confinement",
                "--caselist=mustpass/main/vk-default/api.txt",
            ],
        )

    @patch("subprocess.run")
    def test_returns_subprocess_returncode(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertEqual(
            vk_host.cmd_run_test(
                ["--caselist=mustpass/main/vk-default/api.txt"]
            ),
            1,
        )


class TestGetArchTriple(unittest.TestCase):
    @patch("sysconfig.get_config_var", return_value="x86_64-linux-gnu")
    def test_returns_multiarch_value(self, _cfg):
        self.assertEqual(vk_host.get_arch_triple(), "x86_64-linux-gnu")

    @patch("sysconfig.get_config_var", return_value=None)
    def test_raises_when_multiarch_is_none(self, _cfg):
        with self.assertRaises(RuntimeError):
            vk_host.get_arch_triple()


class TestMain(unittest.TestCase):
    @patch("vk_host.cmd_run_test", return_value=0)
    def test_dispatches_run_test_with_args(self, mock_cmd):
        with patch(
            "sys.argv",
            [
                "vk_host.py",
                "run-test",
                "--caselist=mustpass/main/vk-default/api.txt",
            ],
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
