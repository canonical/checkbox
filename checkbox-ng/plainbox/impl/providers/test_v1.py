# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

"""
plainbox.impl.providers.test_v1
===============================

Test definitions for plainbox.impl.providers.v1 module
"""

from unittest import TestCase
import os

from plainbox.impl.providers.v1 import InsecureProvider1PlugInCollection
from plainbox.impl.providers.v1 import get_insecure_PROVIDERPATH_list
from plainbox.impl.providers.v1 import get_user_PROVIDERPATH_entry
from plainbox.vendor import mock


class Tests(TestCase):

    @mock.patch('os.path.expanduser')
    @mock.patch('os.getenv')
    def test_get_user_PROVIDERPATH_entry__unset_XDG_DATA_HOME(
            self, mock_getenv, mock_expanduser):
        """
        verify that get_user_PROVIDERPATH_entry() still works with unset
        XDG_DATA_HOME
        """
        def getenv(name, default=None):
            if name == 'XDG_DATA_HOME':
                return default
            else:
                self.fail(("no other environment should be consulted"
                           " (asked for {!r})".format(name)))
        mock_getenv.side_effect = getenv

        def expanduser(path):
            return path.replace("~", "/home/user")
        mock_expanduser.side_effect = expanduser
        measured = get_user_PROVIDERPATH_entry()
        expected = "/home/user/.local/share/plainbox-providers-1"
        self.assertEqual(measured, expected)

    @mock.patch('os.path.expanduser')
    @mock.patch('os.getenv')
    def test_get_user_PROVIDERPATH_entry__respects_XDG_DATA_HOME(
            self, mock_getenv, mock_expanduser):
        """
        verify that get_user_PROVIDERPATH_entry() honors XDG_DATA_HOME
        """
        def getenv(name, default=None):
            if name == 'XDG_DATA_HOME':
                return '/home/user/xdg-data'
            else:
                self.fail(("no other environment should be consulted"
                           " (asked for {!r})".format(name)))
        mock_getenv.side_effect = getenv
        measured = get_user_PROVIDERPATH_entry()
        expected = "/home/user/xdg-data/plainbox-providers-1"
        self.assertEqual(measured, expected)

    @mock.patch('plainbox.impl.providers.v1.get_secure_PROVIDERPATH_list')
    @mock.patch('plainbox.impl.providers.v1.get_user_PROVIDERPATH_entry')
    def test_get_insecure_PROVIDERPATH_list(self, mock_guPe, mock_gsPl):
        """
        verify that get_insecure_PROVIDERPATH_list() works
        """
        mock_guPe.return_value = "per-user"
        mock_gsPl.return_value = ["system-wide"]
        self.assertEqual(
            get_insecure_PROVIDERPATH_list(),
            ["system-wide", "per-user"])


class InsecureProvider1PlugInCollectionTests(TestCase):
    """
    Tests for the InsecureProvider1PlugInCollection
    """

    def test_init__without_PROVIDERPATH_set(self):
        """
        validate that InsecureProvider1PlugInCollection() has working defaults
        if PROVIDERPATH are not in env
        """
        real_os_getenv = os.getenv

        def getenv(*args):
            if args[0] == 'PROVIDERPATH':
                return None
            else:
                return real_os_getenv(*args)
        with mock.patch('os.getenv') as mock_getenv:
            mock_getenv.side_effect = getenv
            obj = InsecureProvider1PlugInCollection()
        self.assertTrue(len(obj._dir_list) > 0)

    @mock.patch('os.getenv')
    def test_init__with_PROVIDERPATH_set(self, mock_getenv):
        """
        validate that InsecureProvider1PlugInCollection() respects PROVIDERPATH
        if set in the environment
        """
        mock_getenv.return_value = os.path.pathsep.join(['/foo', '/bar'])
        obj = InsecureProvider1PlugInCollection()
        self.assertTrue(obj._dir_list, ['/foo', '/bar'])
