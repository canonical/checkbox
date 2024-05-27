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

from gl_support import *
from unittest.mock import patch, MagicMock
import unittest


class RemoveColorCode(unittest.TestCase):
    """
    This function should remove color code
    """

    @patch("subprocess.run")
    def test_succ(self, mock_run):
        gs = GLSupport()

        with (
            open("tests/test_data/gl_support_succ.txt", "r") as s,
            open("tests/test_data/gl_support_succ_changed.txt", "r") as sc,
            open("tests/test_data/gl_support_fail.txt", "r") as f,
            open("tests/test_data/gl_support_fail_changed.txt", "r") as fc,
        ):
            s_data = s.read()
            rv = gs.remove_color_code(s_data)
            self.assertEqual(rv, sc.read())
            rv = gs.remove_color_code(f.read())
            self.assertEqual(rv, fc.read())


class IsSupportOpenGLTests(unittest.TestCase):
    """
    This function should execute unity_support_test and remove color code
    from the output
    """

    @patch("subprocess.run")
    def test_succ(self, mock_run):
        gs = GLSupport()
        mock_rv = MagicMock()
        mock_run.return_value = mock_rv
        mock_rv.stdout = ""
        mock_rv.returncode = 0
        gs.is_support_opengl()

    @patch("subprocess.run")
    def test_fail(self, mock_run):
        gs = GLSupport()
        mock_rv = MagicMock()
        mock_run.return_value = mock_rv
        mock_rv.stdout = ""
        mock_rv.returncode = 1
        with self.assertRaises(SystemExit):
            gs.is_support_opengl()

    @patch("subprocess.run")
    def test_command_fail(self, mock_run):
        gs = GLSupport()
        mock_rv = MagicMock()
        mock_run.side_effect = FileNotFoundError
        mock_rv.stdout = ""
        mock_rv.returncode = 1
        with self.assertRaises(SystemExit):
            gs.is_support_opengl()
