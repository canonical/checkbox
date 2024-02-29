#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import unittest
from unittest.mock import patch
from subprocess import CalledProcessError
from check_prerelease import (
    check_kernel_status,
    verify_apt_cache_show,
    verify_apt_cache_showpkg,
    get_apt_cache_information,
    verify_not_lowlatency_kernel
)


class TestGetAptCacheInformation(unittest.TestCase):
    @patch("check_prerelease.check_output")
    def test_get_apt_cache_information_success(self, mock_check_output):
        command = "some_apt_cache_command"
        expected_output = "some_information"
        mock_check_output.return_value = expected_output
        result = get_apt_cache_information(command)
        self.assertEqual(result, expected_output)

    @patch("check_prerelease.check_output")
    def test_get_apt_cache_information_empty_output(self, mock_check_output):
        """Test when getting the empty output from apt-cache showpkg <kernel>
            command
        """
        command = "some_apt_cache_command"
        mock_check_output.return_value = ''

        with self.assertRaises(SystemExit) as context:
            get_apt_cache_information(command)

        self.assertEqual(context.exception.code, 1)

    @patch("check_prerelease.check_output")
    def test_get_apt_cache_information_nonexistent_package(
        self,
        mock_check_output
    ):
        command = "some_apt_cache_command"
        mock_check_output.side_effect = CalledProcessError(
            returncode=0, cmd=command)

        with self.assertRaises(SystemExit) as context:
            get_apt_cache_information(command)

        self.assertEqual(context.exception.code, 1)


class TestVerifyNotLowlatencyKernel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_normal_kernel(self):
        """ Test when the kernel release does not contain "lowlatency" """
        kernel_release = "4.15.0-76-generic"
        result = verify_not_lowlatency_kernel(kernel_release)
        self.assertTrue(result)

    def test_lowlatency_kernel(self):
        """ Test when the kernel release contains "lowlatency" """
        kernel_release = "4.15.0-76-lowlatency"
        result = verify_not_lowlatency_kernel(kernel_release)
        self.assertFalse(result)


class TestVerifyAptCacheShowpkg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    @patch("check_prerelease.get_apt_cache_information")
    @patch("check_prerelease.os")
    def test_verify_apt_cache_showpkg_valid_kernel_from_main_repository(
        self,
        mock_os,
        mock_get_apt_cache_information
    ):
        test_kernel = "1.2.3-generic"
        mock_os.environ.get.return_value = "main"
        mock_get_apt_cache_information.return_value = "ubuntu.com_ubuntu_dists_jammy-updates_main_binary-amd64_Packages"    # noqa E501
        result = verify_apt_cache_showpkg(test_kernel)

        self.assertTrue(result)
        mock_get_apt_cache_information.assert_called_with(
            "apt-cache showpkg linux-image-{}".format(test_kernel))

    @patch("check_prerelease.get_apt_cache_information")
    @patch("check_prerelease.os")
    def test_verify_apt_cache_showpkg_valid_kernel_from_universe_repository(
        self,
        mock_os,
        mock_get_apt_cache_information
    ):
        test_kernel = "1.2.3-generic"
        mock_os.environ.get.return_value = "universe"
        mock_get_apt_cache_information.return_value = "ubuntu.com_ubuntu_dists_jammy-updates_universe_binary-amd64_Packages"    # noqa E501
        result = verify_apt_cache_showpkg(test_kernel)

        self.assertTrue(result)
        mock_get_apt_cache_information.assert_called_with(
            "apt-cache showpkg linux-image-{}".format(test_kernel))

    @patch("check_prerelease.get_apt_cache_information")
    @patch("check_prerelease.os")
    def test_verify_apt_cache_showpkg_invalid_kernel_from_a_ppa(
        self,
        mock_os,
        mock_get_apt_cache_information
    ):
        test_kernel = "1.2.3-generic"
        mock_os.environ.get.return_value = "main"
        mock_get_apt_cache_information.return_value = "ubuntu.com_ubuntu_dists_jammy-updates_main_binary-amd64_Packages\nppa.launchpad.net\n"    # noqa E501
        result = verify_apt_cache_showpkg(test_kernel)

        self.assertFalse(result)
        mock_get_apt_cache_information.assert_called_with(
            "apt-cache showpkg linux-image-{}".format(test_kernel))

    @patch("check_prerelease.get_apt_cache_information")
    @patch("check_prerelease.os")
    def test_verify_apt_cache_showpkg_invalid_kernel_from_invalid_repository(
        self,
        mock_os,
        mock_get_apt_cache_information
    ):
        test_kernel = "1.2.3-generic"
        mock_os.environ.get.return_value = "main"
        mock_get_apt_cache_information.return_value = "ubuntu.com_ubuntu_dists_jammy-updates_OTHER_binary-amd64_Packages"    # noqa E501
        result = verify_apt_cache_showpkg(test_kernel)

        self.assertFalse(result)
        mock_get_apt_cache_information.assert_called_with(
            "apt-cache showpkg linux-image-{}".format(test_kernel))


class TestVerifyAptCacheShow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    @patch("check_prerelease.get_apt_cache_information")
    def test_verify_apt_cache_show_success(
        self,
        mock_get_apt_cache_information
    ):
        mock_get_apt_cache_information.return_value = "Source: linux"
        result = verify_apt_cache_show("kernel_test")
        self.assertTrue(result)

    @patch("check_prerelease.get_apt_cache_information")
    def test_verify_apt_cache_show_non_canonical_kernel(
        self,
        mock_get_apt_cache_information
    ):
        mock_get_apt_cache_information.return_value = "Source: other_source"
        result = verify_apt_cache_show("kernel_test")
        self.assertFalse(result)

    @patch("check_prerelease.get_apt_cache_information")
    def test_verify_apt_cache_show_edge_kernel(
        self,
        mock_get_apt_cache_information
    ):
        mock_get_apt_cache_information.return_value = "Source: linux-signed-hwe-edge"    # noqa E501
        result = verify_apt_cache_show("kernel_test")
        self.assertFalse(result)
        mock_get_apt_cache_information.return_value = "Source: linux-hwe-edge"
        result = verify_apt_cache_show("kernel_test")
        self.assertFalse(result)


class TestCheckKernelStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    @patch("check_prerelease.platform")
    @patch("check_prerelease.verify_not_lowlatency_kernel")
    @patch("check_prerelease.verify_apt_cache_showpkg")
    @patch("check_prerelease.verify_apt_cache_show")
    def test_check_kernel_status_valid_kernel(
        self,
        mock_verify_show,
        mock_verify_showpkg,
        mock_verify_not_lowlatency_kernel,
        mock_platform
    ):
        test_kernel = "99.98.0-generic"
        mock_platform.release.return_value = test_kernel
        mock_verify_showpkg.return_value = True
        mock_verify_show.return_value = True
        mock_verify_not_lowlatency_kernel.return_value = True

        result = check_kernel_status()

        self.assertTrue(result)
        mock_verify_showpkg.assert_called_with(test_kernel)
        mock_verify_show.assert_called_with(test_kernel)
        mock_verify_not_lowlatency_kernel.assert_called_with(test_kernel)

    @patch("check_prerelease.platform")
    @patch("check_prerelease.verify_not_lowlatency_kernel")
    @patch("check_prerelease.verify_apt_cache_showpkg")
    @patch("check_prerelease.verify_apt_cache_show")
    def test_check_kernel_status_invalid_kernel(
        self,
        mock_verify_show,
        mock_verify_showpkg,
        mock_verify_not_lowlatency_kernel,
        mock_platform
    ):
        test_kernel = "123-generic"
        mock_platform.release.return_value = test_kernel
        mock_verify_showpkg.return_value = True
        mock_verify_show.return_value = False
        mock_verify_not_lowlatency_kernel.return_value = True

        result = check_kernel_status()

        self.assertFalse(result)
        mock_verify_showpkg.assert_called_with(test_kernel)
        mock_verify_show.assert_called_with(test_kernel)
        mock_verify_not_lowlatency_kernel.assert_called_with(test_kernel)
