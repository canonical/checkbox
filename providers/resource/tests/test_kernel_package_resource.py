#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Authors:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
from unittest.mock import Mock, call, patch

from kernel_package_resource import get_kernel_package_info, main


class TestKernelPackageResource(unittest.TestCase):

    @patch("kernel_package_resource.on_ubuntucore")
    @patch("kernel_package_resource.get_kernel_snap")
    def test_get_kernel_package_info_core(
        self, mock_get_kernel_snap, mock_on_ubuntucore
    ):
        "Test the function to get the kernel package info on Ubuntu Core"
        mock_get_kernel_snap.return_value = "pc-kernel"
        mock_on_ubuntucore.return_value = True
        result = get_kernel_package_info()
        self.assertEqual(result, ("pc-kernel", "snap"))

    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname")
    def test_get_kernel_package_info_non_core(
        self, mock_uname, mock_check_output
    ):
        "Test the function to get the kernel package info on classic"
        apt_result = (
            "Package: linux-modules-6.8.0-57-generic\n"
            "Architecture: amd64\n"
            "Version: 6.8.0-57.59\n"
            "Priority: optional\n"
            "Section: kernel\n"
            "Source: linux\n"
            "Origin: Ubuntu\n"
        )
        mock_uname.return_value.release = "6.8.0-57-generic"
        mock_check_output.return_value = apt_result
        result = get_kernel_package_info()
        self.assertEqual(result, ("linux", "deb"))

    @patch("kernel_package_resource.get_release_info")
    @patch("kernel_package_resource.get_kernel_package_info")
    def test_main(self, mock_get_kernel_package_info, mock_get_release_info):
        "Test the main function"
        mock_get_release_info.return_value = {"release": "22.04"}
        mock_get_kernel_package_info.return_value = ("linux", "deb")
        with patch("builtins.print") as mock_print:
            main()

        mock_print.assert_has_calls(
            [call("name: linux"), call("type: deb"), call("release: 22.04")]
        )

    @patch("kernel_package_resource.get_release_info")
    def test_main_no_release(self, mock_get_release_info):
        "Test the main function with no release"
        mock_get_release_info.return_value = {}
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(
            str(cm.exception), "Unable to get release information."
        )

    @patch("kernel_package_resource.get_release_info", Mock())
    @patch("kernel_package_resource.get_kernel_package_info")
    def test_main_no_kernel_package(self, mock_get_kernel_package_info):
        "Test the main function with no kernel package"
        mock_get_kernel_package_info.return_value = (None, None)
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(str(cm.exception), "No kernel package found.")
