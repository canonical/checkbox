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
plainbox.impl.test_plugins
==========================

Test definitions for plainbox.impl.plugins module
"""

from unittest import TestCase
import os

from plainbox.impl.plugins import FsPlugInCollection
from plainbox.impl.plugins import IPlugIn, PlugIn
from plainbox.impl.plugins import PkgResourcesPlugInCollection
from plainbox.vendor import mock


class PlugInTests(TestCase):

    def test_smoke(self):
        obj = mock.Mock()
        # Create a plug-in
        plugin = PlugIn("name", obj)
        # Ensure that plugin name and plugin object are okay
        self.assertEqual(plugin.plugin_name, "name")
        self.assertEqual(plugin.plugin_object, obj)

    def test_base_cls(self):
        self.assertTrue(issubclass(PlugIn, IPlugIn))


class PkgResourcesPlugInCollectionTests(TestCase):

    _NAMESPACE = "namespace"

    def setUp(self):
        # Create a collection
        self.col = PkgResourcesPlugInCollection(self._NAMESPACE)

    def test_namespace_is_set(self):
        # Ensure that namespace was saved
        self.assertEqual(self.col._namespace, self._NAMESPACE)

    def test_plugins_are_empty(self):
        # Ensure that plugins start out empty
        self.assertEqual(len(self.col._plugins), 0)

    def test_initial_loaded_flag(self):
        # Ensure that 'loaded' flag is false
        self.assertFalse(self.col._loaded)

    def test_default_wrapper(self):
        # Ensure that the wrapper is :class:`PlugIn`
        self.assertEqual(self.col._wrapper, PlugIn)

    @mock.patch('pkg_resources.iter_entry_points')
    def test_load(self, mock_iter):
        # Create a mocked entry point
        mock_ep1 = mock.Mock()
        mock_ep1.name = "zzz"
        mock_ep1.load.return_value = "two"
        # Create another mocked entry point
        mock_ep2 = mock.Mock()
        mock_ep2.name = "aaa"
        mock_ep2.load.return_value = "one"
        # Make the collection load both mocked entry points
        mock_iter.return_value = [mock_ep1, mock_ep2]
        # Load plugins
        self.col.load()
        # Ensure that pkg_resources were interrogated
        mock_iter.assert_calledwith(self._NAMESPACE)
        # Ensure that both entry points were loaded
        mock_ep1.load.assert_called_with()
        mock_ep2.load.assert_called_with()

    @mock.patch('plainbox.impl.plugins.logger')
    @mock.patch('pkg_resources.iter_entry_points')
    def test_load_failing(self, mock_iter, mock_logger):
        # Create a mocked entry point
        mock_ep1 = mock.Mock()
        mock_ep1.name = "zzz"
        mock_ep1.load.return_value = "two"
        # Create another mockeed antry point
        mock_ep2 = mock.Mock()
        mock_ep2.name = "aaa"
        mock_ep2.load.side_effect = ImportError("boom")
        # Make the collection load both mocked entry points
        mock_iter.return_value = [mock_ep1, mock_ep2]
        # Load plugins
        self.col.load()
        # Ensure that pkg_resources were interrogated
        mock_iter.assert_calledwith(self._NAMESPACE)
        # Ensure that both entry points were loaded
        mock_ep1.load.assert_called_with()
        mock_ep2.load.assert_called_with()
        # Ensure that an exception was logged
        mock_logger.exception.assert_called_with(
            "Unable to import %s", mock_ep2)

    def test_fake_plugins(self):
        # Create a mocked entry plugin
        plug1 = PlugIn("ep1", "obj1")
        plug2 = PlugIn("ep2", "obj2")
        # With fake plugins
        with self.col.fake_plugins([plug1, plug2]):
            # Check that plugins are correct
            self.assertIs(self.col.get_by_name('ep1'), plug1)
            self.assertIs(self.col.get_by_name('ep2'), plug2)
            # Access all plugins
            self.assertEqual(self.col.get_all_plugins(), [plug1, plug2])
            # Access all plugin names
            self.assertEqual(self.col.get_all_names(), ['ep1', 'ep2'])
            # Access all pairs (name, plugin)
            self.assertEqual(self.col.get_all_items(),
                             [('ep1', plug1), ('ep2', plug2)])


class FsPlugInCollectionTests(TestCase):

    _P1 = "/system/providers"
    _P2 = "home/user/.providers"
    _PATH = os.path.pathsep.join([_P1, _P2])
    _EXT = ".plugin"

    def setUp(self):
        # Create a collection
        self.col = FsPlugInCollection(self._PATH, self._EXT)

    def test_path_is_set(self):
        # Ensure that path was saved
        self.assertEqual(self.col._path, self._PATH)

    def test_ext_is_set(self):
        # Ensure that ext was saved
        self.assertEqual(self.col._ext, self._EXT)

    def test_plugins_are_empty(self):
        # Ensure that plugins start out empty
        self.assertEqual(len(self.col._plugins), 0)

    def test_initial_loaded_flag(self):
        # Ensure that 'loaded' flag is false
        self.assertFalse(self.col._loaded)

    def test_default_wrapper(self):
        # Ensure that the wrapper is :class:`PlugIn`
        self.assertEqual(self.col._wrapper, PlugIn)

    @mock.patch('plainbox.impl.plugins.logger')
    @mock.patch('builtins.open')
    @mock.patch('os.path.isfile')
    @mock.patch('os.listdir')
    def test_load(self, mock_listdir, mock_isfile, mock_open, mock_logger):
        # Mock a bit of filesystem access methods to make some plugins show up
        def fake_listdir(path):
            if path == self._P1:
                return [
                    # A regular plugin
                    'foo.plugin',
                    # Another regular plugin
                    'bar.plugin',
                    # Unrelated file, not a plugin
                    'unrelated.txt',
                    # A directory that looks like a plugin
                    'dir.bad.plugin',
                    # A plugin without read permissions
                    'noperm.plugin']
            else:
                raise OSError("There is nothing in {}".format(path))

        def fake_isfile(path):
            return not os.path.basename(path).startswith('dir.')

        def fake_open(path, encoding=None, mode=None):
            m = mock.Mock()
            m.__enter__ = mock.Mock()
            m.__exit__ = mock.Mock()
            if path == os.path.join(self._P1, 'foo.plugin'):
                m.read.return_value = "foo"
                return m
            elif path == os.path.join(self._P1, 'bar.plugin'):
                m.read.return_value = "bar"
                return m
            elif path == os.path.join(self._P1, 'noperm.plugin'):
                raise IOError("You cannot open this file")
            else:
                raise IOError("Unexpected file: {}".format(path))
        mock_listdir.side_effect = fake_listdir
        mock_isfile.side_effect = fake_isfile
        mock_open.side_effect = fake_open
        # Load all plugins now
        self.col.load()
        # And 'again', just to ensure we're doing the IO only once
        self.col.load()
        # Ensure that we actually tried to look at the filesytstem
        self.assertEqual(
            mock_listdir.call_args_list, [
                ((self._P1, ), {}),
                ((self._P2, ), {})
            ])
        # Ensure that we actually tried to check if things are files
        self.assertEqual(
            mock_isfile.call_args_list, [
                ((os.path.join(self._P1, 'foo.plugin'),), {}),
                ((os.path.join(self._P1, 'bar.plugin'),), {}),
                ((os.path.join(self._P1, 'dir.bad.plugin'),), {}),
                ((os.path.join(self._P1, 'noperm.plugin'),), {}),
            ])
        # Ensure that we actually tried to open some files
        self.assertEqual(
            mock_open.call_args_list, [
                ((os.path.join(self._P1, 'bar.plugin'),),
                 {'encoding': 'UTF-8'}),
                ((os.path.join(self._P1, 'foo.plugin'),),
                 {'encoding': 'UTF-8'}),
                ((os.path.join(self._P1, 'noperm.plugin'),),
                 {'encoding': 'UTF-8'}),
            ])
        # Ensure that an exception was logged
        mock_logger.error.assert_called_with(
            'Unable to load %r: %s',
            '/system/providers/noperm.plugin',
            'You cannot open this file')
