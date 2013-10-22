# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.providers.test_v1
===============================

Test definitions for plainbox.impl.providers.v1 module
"""

from unittest import TestCase
import os.path

from plainbox.impl.providers.v1 import get_default_PROVIDERPATH
from plainbox.vendor import mock


class Tests(TestCase):

    @mock.patch('os.path.expanduser')
    @mock.patch('os.getenv')
    def test_get_default_PROVIDERPATH(self, mock_getenv, mock_expanduser):
        """
        verify that unset XDG_DATA_HOME still works
        """
        def getenv(name, default=None):
            if name == 'XDG_DATA_HOME':
                return default
            else:
                self.fail("no other environment should be consulted (asked for %r)" % name)
        mock_getenv.side_effect = getenv

        def expanduser(path):
            return path.replace("~", "/home/user")
        mock_expanduser.side_effect = expanduser
        measured = get_default_PROVIDERPATH()
        expected = os.pathsep.join([
            "/usr/share/plainbox-providers-1",
            "/home/user/.local/share/plainbox-providers-1"])
        self.assertEqual(measured, expected)

    @mock.patch('os.path.expanduser')
    @mock.patch('os.getenv')
    def test_get_default_PROVIDERPATH_respects_XDG_DATA_HOME(
            self, mock_getenv, mock_expanduser):
        """
        verify that XDG_DATA_HOME is honored
        """
        def getenv(name, default=None):
            if name == 'XDG_DATA_HOME':
                return '/home/user/xdg-data'
            else:
                self.fail("no other environment should be consulted")
        mock_getenv.side_effect = getenv
        measured = get_default_PROVIDERPATH()
        expected = os.pathsep.join([
            "/usr/share/plainbox-providers-1",
            "/home/user/xdg-data/plainbox-providers-1"])
        self.assertEqual(measured, expected)
