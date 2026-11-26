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

import subprocess
import unittest
from unittest.mock import Mock, call, mock_open, patch

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

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname")
    @patch("kernel_package_resource.add_hostfs_prefix")
    def test_get_kernel_package_info_non_core(
        self, mock_add_hostfs_prefix, mock_uname, mock_check_output
    ):
        "Test the function to get the kernel package info on classic"
        mock_add_hostfs_prefix.return_value = "/var/lib/dpkg"
        mock_uname.return_value.release = "6.8.0-57-generic"
        mock_check_output.return_value = "installed\tlinux\n"
        result = get_kernel_package_info()
        self.assertEqual(result, ("linux", "deb"))
        mock_add_hostfs_prefix.assert_called_once_with("/var/lib/dpkg")
        mock_check_output.assert_called_once_with(
            [
                "dpkg-query",
                "--admindir",
                "/var/lib/dpkg",
                "-W",
                "-f=${db:Status-Status}\t${source:Package}\n",
                "linux-modules-6.8.0-57-generic",
            ],
            universal_newlines=True,
        )

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname")
    @patch("kernel_package_resource.add_hostfs_prefix")
    def test_get_kernel_package_info_in_strict_snap(
        self, mock_add_hostfs_prefix, mock_uname, mock_check_output
    ):
        mock_add_hostfs_prefix.return_value = (
            "/var/lib/snapd/hostfs/var/lib/dpkg"
        )
        mock_uname.return_value.release = "6.8.0-57-generic"
        mock_check_output.return_value = "installed\tlinux-hwe-6.8\n"
        self.assertEqual(get_kernel_package_info(), ("linux-hwe-6.8", "deb"))
        self.assertEqual(
            mock_check_output.call_args[0][0][2],
            "/var/lib/snapd/hostfs/var/lib/dpkg",
        )

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname", Mock())
    @patch(
        "kernel_package_resource.add_hostfs_prefix",
        Mock(return_value="/var/lib/dpkg"),
    )
    @patch("builtins.open", mock_open(read_data="dpkg status"))
    def test_get_kernel_package_info_non_core_not_found(
        self, mock_check_output
    ):
        "Test classic when the modules package is unknown (e.g. container)"
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "dpkg-query"
        )
        self.assertEqual(get_kernel_package_info(), (None, "deb"))

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname", Mock())
    @patch(
        "kernel_package_resource.add_hostfs_prefix",
        Mock(return_value="/missing/var/lib/dpkg"),
    )
    @patch("builtins.open", side_effect=FileNotFoundError("dpkg status"))
    def test_get_kernel_package_info_missing_database(
        self, _, mock_check_output
    ):
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "dpkg-query"
        )
        with self.assertRaises(FileNotFoundError):
            get_kernel_package_info()

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname", Mock())
    @patch("kernel_package_resource.add_hostfs_prefix", Mock())
    def test_get_kernel_package_info_dpkg_error(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(
            2, "dpkg-query"
        )
        with self.assertRaises(subprocess.CalledProcessError):
            get_kernel_package_info()

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname", Mock())
    @patch("kernel_package_resource.add_hostfs_prefix", Mock())
    def test_get_kernel_package_info_non_core_not_installed(
        self, mock_check_output
    ):
        mock_check_output.return_value = "config-files\tlinux\n"
        self.assertEqual(get_kernel_package_info(), (None, "deb"))

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname", Mock())
    @patch("kernel_package_resource.add_hostfs_prefix", Mock())
    def test_get_kernel_package_info_non_core_no_source(
        self, mock_check_output
    ):
        "Test classic when the package has no source name"
        mock_check_output.return_value = "installed\t\n"
        self.assertEqual(get_kernel_package_info(), (None, "deb"))

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.subprocess.check_output")
    @patch("kernel_package_resource.os.uname", Mock())
    @patch("kernel_package_resource.add_hostfs_prefix", Mock())
    def test_get_kernel_package_info_without_dpkg_query(
        self, mock_check_output
    ):
        mock_check_output.side_effect = FileNotFoundError("dpkg-query")
        with self.assertRaises(SystemExit) as exc:
            get_kernel_package_info()
        self.assertEqual(str(exc.exception), "Unable to find dpkg-query.")

    @patch("kernel_package_resource.on_ubuntucore", Mock(return_value=False))
    @patch("kernel_package_resource.os.uname", Mock())
    @patch("kernel_package_resource.add_hostfs_prefix")
    def test_get_kernel_package_info_inaccessible_snap_metadata(
        self, mock_add_hostfs_prefix
    ):
        mock_add_hostfs_prefix.side_effect = PermissionError("snap metadata")
        with self.assertRaises(PermissionError):
            get_kernel_package_info()

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
