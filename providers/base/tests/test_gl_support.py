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

    unchanged = r"""
OpenGL vendor string:   Intel
OpenGL renderer string: Mesa Intel(R) Arc(tm) Graphics (MTL)
OpenGL version string:4.6 (Compatibility Profile)Mesa 23.2.1-1ubuntu3.1~22.04.2

Not software rendered:    [32;01myes[00m
Not blacklisted:          [32;01myes[00m
GLX fbconfig:             [32;01myes[00m
GLX texture from pixmap:  [32;01myes[00m
GL npot or rect textures: [32;01myes[00m
GL vertex program:        [32;01myes[00m
GL fragment program:      [32;01myes[00m
GL vertex buffer object:  [32;01myes[00m
GL framebuffer object:    [32;01myes[00m
GL version is 1.4+:       [32;01myes[00m

Unity 3D supported:       [32;01myes[00m
"""
    changed = r"""
OpenGL vendor string:   Intel
OpenGL renderer string: Mesa Intel(R) Arc(tm) Graphics (MTL)
OpenGL version string:4.6 (Compatibility Profile)Mesa 23.2.1-1ubuntu3.1~22.04.2

Not software rendered:    yes
Not blacklisted:          yes
GLX fbconfig:             yes
GLX texture from pixmap:  yes
GL npot or rect textures: yes
GL vertex program:        yes
GL fragment program:      yes
GL vertex buffer object:  yes
GL framebuffer object:    yes
GL version is 1.4+:       yes

Unity 3D supported:       yes
"""

    @patch("subprocess.run")
    def test_succ(self, mock_run):
        gs = GLSupport()
        rv = gs.remove_color_code(self.unchanged)
        self.assertEqual(rv, self.changed)


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
