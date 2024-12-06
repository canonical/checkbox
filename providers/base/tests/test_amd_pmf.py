#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

from amd_pmf import *
from unittest.mock import patch
import unittest


class IsPMFLoadedTests(unittest.TestCase):
    """
    This function should validate the amd_pmf is shown in the output
    of lsmod
    """

    with_pmf_output = """
Module                  Size  Used by
amd_pmf               155648  0
rfcomm                102400  4
ccm                    20480  9
vhost_vsock            24576  0
    """

    without_pmf_output = """
Module                  Size  Used by
tls                   155648  0
rfcomm                102400  4
ccm                    20480  9
vhost_vsock            24576  0
    """

    @patch("subprocess.check_output")
    def test_succ(self, mock_output):
        ap = AMDPMF()
        mock_output.return_value = self.with_pmf_output
        ap.is_pmf_loaded()

    @patch("subprocess.check_output")
    def test_fail(self, mock_output):
        ap = AMDPMF()
        mock_output.return_value = self.without_pmf_output
        with self.assertRaises(SystemExit):
            ap.is_pmf_loaded()

    @patch("subprocess.check_output")
    def test_command_fail(self, mock_output):
        ap = AMDPMF()
        mock_output.side_effect = FileNotFoundError
        with self.assertRaises(SystemExit):
            ap.is_pmf_loaded()
