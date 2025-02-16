#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
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

from unittest.mock import patch
import unittest
from amd_pmf import check_pmf_loaded


class CheckPMFLoadedTests(unittest.TestCase):
    """
    This function should validate that amd_pmf is shown in the output
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
        mock_output.return_value = self.with_pmf_output
        check_pmf_loaded()

    @patch("subprocess.check_output")
    def test_fail(self, mock_output):
        mock_output.return_value = self.without_pmf_output
        with self.assertRaises(SystemExit):
            check_pmf_loaded()

    @patch("subprocess.check_output")
    def test_command_fail(self, mock_output):
        """Test outcome when `lsmod` command is not available"""
        mock_output.side_effect = FileNotFoundError
        with self.assertRaises(SystemExit):
            check_pmf_loaded()
