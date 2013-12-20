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
plainbox.impl.secure.test_plugins
=================================

Test definitions for plainbox.impl.secure.plugins module
"""

from unittest import TestCase
import collections
import os

from plainbox.impl.secure.plugins import FsPlugInCollection
from plainbox.impl.secure.plugins import IPlugIn, PlugIn
from plainbox.impl.secure.plugins import PkgResourcesPlugInCollection
from plainbox.impl.secure.plugins import PlugInCollectionBase
from plainbox.vendor import mock


class PlugInTests(TestCase):
    """
    Tests for PlugIn class
    """

    NAME = "name"
    OBJ = mock.Mock(name="obj")

    def setUp(self):
        self.plugin = PlugIn(self.NAME, self.OBJ)

    def test_property_name(self):
        """
        verify that PlugIn.plugin_name getter works
        """
        self.assertEqual(self.plugin.plugin_name, self.NAME)

    def test_property_object(self):
        """
        verify that PlugIn.plugin_object getter works
        """
        self.assertEqual(self.plugin.plugin_object, self.OBJ)

    def test_repr(self):
        """
        verify that repr for PlugIn works
        """
        self.assertEqual(repr(self.plugin), "<PlugIn plugin_name:'name'>")

    def test_base_cls(self):
        """
        verify that PlugIn inherits IPlugIn
        """
        self.assertTrue(issubclass(PlugIn, IPlugIn))


class DummyPlugInCollection(PlugInCollectionBase):
    """
    A dummy, concrete subclass of PlugInCollectionBase
    """

    def load(self):
        """
        dummy implementation of load()

        :raises NotImplementedError:
            always raised
        """
        raise NotImplementedError("this is a dummy method")


class PlugInCollectionBaseTests(TestCase):
    """
    Tests for PlugInCollectionBase class.

    Since this is an abstract class we're creating a concrete subclass with
    dummy implementation of the load() method.
    """

    def setUp(self):
        self.col = DummyPlugInCollection()
        self.plug1 = PlugIn("name1", "obj1")
        self.plug2 = PlugIn("name2", "obj2")

    @mock.patch.object(DummyPlugInCollection, "load")
    def test_auto_loading(self, mock_col):
        """
        verify that PlugInCollectionBase.load() is called when load=True is
        passed to the initializer.
        """
        col = DummyPlugInCollection(load=True)
        col.load.assert_called()

    def test_defaults(self):
        """
        verify what defaults are passed to the initializer or set internally
        """
        self.assertEqual(self.col._wrapper, PlugIn)
        self.assertEqual(self.col._plugins, collections.OrderedDict())
        self.assertEqual(self.col._loaded, False)
        self.assertEqual(self.col._mocked_objects, None)

    def test_get_by_name__typical(self):
        """
        verify that PlugInCollectionBase.get_by_name() works
        """
        with self.col.fake_plugins([self.plug1]):
            self.assertEqual(
                self.col.get_by_name(self.plug1.plugin_name), self.plug1)

    def test_get_by_name__missing(self):
        """
        check how PlugInCollectionBase.get_by_name() behaves when there is no
        match for the given name.
        """
        with self.assertRaises(KeyError), self.col.fake_plugins([]):
            self.col.get_by_name(self.plug1.plugin_name)

    def test_get_all_names(self):
        """
        verify that PlugInCollectionBase.get_all_names() works
        """
        with self.col.fake_plugins([self.plug1, self.plug2]):
            self.assertEqual(
                self.col.get_all_names(),
                [self.plug1.plugin_name, self.plug2.plugin_name])

    def test_get_all_plugins(self):
        """
        verify that PlugInCollectionBase.get_all_plugins() works
        """
        with self.col.fake_plugins([self.plug1, self.plug2]):
            self.assertEqual(
                self.col.get_all_plugins(), [self.plug1, self.plug2])

    def test_get_items(self):
        """
        verify that PlugInCollectionBase.get_all_items() works
        """
        with self.col.fake_plugins([self.plug1, self.plug2]):
            self.assertEqual(
                self.col.get_all_items(),
                [(self.plug1.plugin_name, self.plug1),
                 (self.plug2.plugin_name, self.plug2)])

    def test_fake_plugins(self):
        """
        verify that PlugInCollectionBase.fake_plugins() works
        """
        # create a canary object we'll check for below
        canary = object()
        # store it to all the attributes we expect to see changed by
        # fake_plugins()
        self.col._loaded = canary
        self.col._plugins = canary
        # use fake_plugins() with some plugins we have
        with self.col.fake_plugins([self.plug1, self.plug2]):
            # ensure that we don't have canaries here
            self.assertEqual(self.col._loaded, True)
            self.assertEqual(self.col._plugins, collections.OrderedDict([
                (self.plug1.plugin_name, self.plug1),
                (self.plug2.plugin_name, self.plug2)]))
        # ensure that we see canaries outside of the context manager
        self.assertEqual(self.col._loaded, canary)
        self.assertEqual(self.col._plugins, canary)

    def test_wrap_and_add_plugin(self):
        """
        verify that PlugInCollectionBase.wrap_and_add_plugin() works
        """
        self.col.wrap_and_add_plugin("new-name", "new-obj")
        self.assertIn("new-name", self.col._plugins)
        self.assertEqual(
            self.col._plugins["new-name"].plugin_name, "new-name")
        self.assertEqual(
            self.col._plugins["new-name"].plugin_object, "new-obj")


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

    @mock.patch('plainbox.impl.secure.plugins.logger')
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

    @mock.patch('plainbox.impl.secure.plugins.logger')
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
