# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
from plainbox.impl.secure.plugins import PlugInError
from plainbox.vendor import mock


class PlugInTests(TestCase):
    """
    Tests for PlugIn class
    """

    NAME = "name"
    OBJ = mock.Mock(name="obj")
    LOAD_TIME = 42

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

    def test_plugin_load_time(self):
        """
        verify that PlugIn.plugin_load_time getter works
        """
        self.assertEqual(PlugIn(self.NAME, self.OBJ).plugin_load_time, 0)
        self.assertEqual(
            PlugIn(self.NAME, self.OBJ, self.LOAD_TIME).plugin_load_time,
            self.LOAD_TIME,
        )

    def test_plugin_wrap_time(self):
        """
        verify that PlugIn.plugin_wrap_time getter works
        """
        self.assertEqual(self.plugin.plugin_wrap_time, 0)

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

    LOAD_TIME = 42

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
        col.load.assert_called_once_with()

    def test_defaults(self):
        """
        verify what defaults are passed to the initializer or set internally
        """
        self.assertEqual(self.col._wrapper, PlugIn)
        self.assertEqual(self.col._plugins, collections.OrderedDict())
        self.assertEqual(self.col._loaded, False)
        self.assertEqual(self.col._problem_list, [])

    def test_get_by_name__typical(self):
        """
        verify that PlugInCollectionBase.get_by_name() works
        """
        with self.col.fake_plugins([self.plug1]):
            self.assertEqual(
                self.col.get_by_name(self.plug1.plugin_name), self.plug1
            )

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
                [self.plug1.plugin_name, self.plug2.plugin_name],
            )

    def test_get_all_plugins(self):
        """
        verify that PlugInCollectionBase.get_all_plugins() works
        """
        with self.col.fake_plugins([self.plug1, self.plug2]):
            self.assertEqual(
                self.col.get_all_plugins(), [self.plug1, self.plug2]
            )

    def test_get_all_plugin_objects(self):
        """
        verify that PlugInCollectionBase.get_all_plugin_objects() works
        """
        with self.col.fake_plugins([self.plug1, self.plug2]):
            self.assertEqual(
                self.col.get_all_plugin_objects(),
                [self.plug1.plugin_object, self.plug2.plugin_object],
            )

    def test_get_items(self):
        """
        verify that PlugInCollectionBase.get_all_items() works
        """
        with self.col.fake_plugins([self.plug1, self.plug2]):
            self.assertEqual(
                self.col.get_all_items(),
                [
                    (self.plug1.plugin_name, self.plug1),
                    (self.plug2.plugin_name, self.plug2),
                ],
            )

    def test_problem_list(self):
        """
        verify that PlugInCollectionBase.problem_list works
        """
        self.assertIs(self.col.problem_list, self.col._problem_list)

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
        self.col._problems = canary
        # use fake_plugins() with some plugins we have
        fake_plugins = [self.plug1, self.plug2]
        with self.col.fake_plugins(fake_plugins):
            # ensure that we don't have canaries here
            self.assertEqual(self.col._loaded, True)
            self.assertEqual(
                self.col._plugins,
                collections.OrderedDict(
                    [
                        (self.plug1.plugin_name, self.plug1),
                        (self.plug2.plugin_name, self.plug2),
                    ]
                ),
            )
            self.assertEqual(self.col._problem_list, [])
        # ensure that we see canaries outside of the context manager
        self.assertEqual(self.col._loaded, canary)
        self.assertEqual(self.col._plugins, canary)
        self.assertEqual(self.col._problems, canary)

    def test_fake_plugins__with_problem_list(self):
        """
        verify that PlugInCollectionBase.fake_plugins() works when called with
        the optional problem list.
        """
        # create a canary object we'll check for below
        canary = object()
        # store it to all the attributes we expect to see changed by
        # fake_plugins()
        self.col._loaded = canary
        self.col._plugins = canary
        self.col._problems = canary
        # use fake_plugins() with some plugins we have
        fake_plugins = [self.plug1, self.plug2]
        fake_problems = [PlugInError("just testing")]
        with self.col.fake_plugins(fake_plugins, fake_problems):
            # ensure that we don't have canaries here
            self.assertEqual(self.col._loaded, True)
            self.assertEqual(
                self.col._plugins,
                collections.OrderedDict(
                    [
                        (self.plug1.plugin_name, self.plug1),
                        (self.plug2.plugin_name, self.plug2),
                    ]
                ),
            )
            self.assertEqual(self.col._problem_list, fake_problems)
        # ensure that we see canaries outside of the context manager
        self.assertEqual(self.col._loaded, canary)
        self.assertEqual(self.col._plugins, canary)
        self.assertEqual(self.col._problems, canary)

    def test_wrap_and_add_plugin__normal(self):
        """
        verify that PlugInCollectionBase.wrap_and_add_plugin() works
        """
        self.col.wrap_and_add_plugin("new-name", "new-obj", self.LOAD_TIME)
        self.assertIn("new-name", self.col._plugins)
        self.assertEqual(self.col._plugins["new-name"].plugin_name, "new-name")
        self.assertEqual(
            self.col._plugins["new-name"].plugin_object, "new-obj"
        )
        self.assertEqual(
            self.col._plugins["new-name"].plugin_load_time, self.LOAD_TIME
        )

    @mock.patch("plainbox.impl.secure.plugins.logger")
    def test_wrap_and_add_plugin__problem(self, mock_logger):
        """
        verify that PlugInCollectionBase.wrap_and_add_plugin() works when a
        problem occurs.
        """
        with mock.patch.object(self.col, "_wrapper") as mock_wrapper:
            mock_wrapper.side_effect = PlugInError
            self.col.wrap_and_add_plugin("new-name", "new-obj", self.LOAD_TIME)
            mock_wrapper.assert_called_with(
                "new-name", "new-obj", self.LOAD_TIME
            )
        self.assertIsInstance(self.col.problem_list[0], PlugInError)
        self.assertNotIn("new-name", self.col._plugins)
        mock_logger.warning.assert_called_once_with(
            "Unable to prepare plugin %s: %s", "new-name", PlugInError()
        )

    def test_extra_wrapper_args(self):
        """
        verify that PlugInCollectionBase passes extra arguments to the wrapper
        """

        class TestPlugIn(PlugIn):

            def __init__(self, name, obj, load_time, *args, **kwargs):
                super().__init__(name, obj, load_time)
                self.args = args
                self.kwargs = kwargs

        col = DummyPlugInCollection(
            False, TestPlugIn, 1, 2, 3, some="argument"
        )
        col.wrap_and_add_plugin("name", "obj", self.LOAD_TIME)
        self.assertEqual(col._plugins["name"].args, (1, 2, 3))
        self.assertEqual(col._plugins["name"].kwargs, {"some": "argument"})


class PkgResourcesPlugInCollectionTests(TestCase):
    """
    Tests for PlugInCollectionBase class
    """

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

    @mock.patch("pkg_resources.iter_entry_points")
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
        mock_iter.assert_called_with(self._NAMESPACE)
        # Ensure that both entry points were loaded
        mock_ep1.load.assert_called_with()
        mock_ep2.load.assert_called_with()

    @mock.patch("plainbox.impl.secure.plugins.logger")
    @mock.patch("pkg_resources.iter_entry_points")
    def test_load_failing(self, mock_iter, mock_logger):
        # Create a mocked entry point
        mock_ep1 = mock.Mock()
        mock_ep1.name = "zzz"
        mock_ep1.load.return_value = "two"
        # Create another mocked entry point
        mock_ep2 = mock.Mock()
        mock_ep2.name = "aaa"
        mock_ep2.load.side_effect = ImportError("boom")
        # Make the collection load both mocked entry points
        mock_iter.return_value = [mock_ep1, mock_ep2]
        # Load plugins
        self.col.load()
        # Ensure that pkg_resources were interrogated
        mock_iter.assert_called_with(self._NAMESPACE)
        # Ensure that both entry points were loaded
        mock_ep1.load.assert_called_with()
        mock_ep2.load.assert_called_with()
        # Ensure that an exception was logged
        mock_logger.exception.assert_called_with(
            "Unable to import %s", mock_ep2
        )
        # Ensure that the error was collected
        self.assertIsInstance(self.col.problem_list[0], ImportError)


class FsPlugInCollectionTests(TestCase):

    _P1 = "/system/providers"
    _P2 = "home/user/.providers"
    _DIR_LIST = [_P1, _P2]
    _EXT = ".plugin"

    def setUp(self):
        # Create a collection
        self.col = FsPlugInCollection(self._DIR_LIST, self._EXT)

    def test_path_is_set(self):
        # Ensure that path was saved
        self.assertEqual(self.col._dir_list, self._DIR_LIST)

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

    @mock.patch("plainbox.impl.secure.plugins.logger")
    @mock.patch("builtins.open")
    @mock.patch("os.path.isfile")
    @mock.patch("os.listdir")
    def test_load(self, mock_listdir, mock_isfile, mock_open, mock_logger):
        # Mock a bit of filesystem access methods to make some plugins show up
        def fake_listdir(path):
            if path == self._P1:
                return [
                    # A regular plugin
                    "foo.plugin",
                    # Another regular plugin
                    "bar.plugin",
                    # Unrelated file, not a plugin
                    "unrelated.txt",
                    # A directory that looks like a plugin
                    "dir.bad.plugin",
                    # A plugin without read permissions
                    "noperm.plugin",
                ]
            else:
                raise OSError("There is nothing in {}".format(path))

        def fake_isfile(path):
            return not os.path.basename(path).startswith("dir.")

        def fake_open(path, encoding=None, mode=None):
            m = mock.MagicMock(name="opened file {!r}".format(path))
            m.__enter__.return_value = m
            if path == os.path.join(self._P1, "foo.plugin"):
                m.read.return_value = "foo"
                return m
            elif path == os.path.join(self._P1, "bar.plugin"):
                m.read.return_value = "bar"
                return m
            elif path == os.path.join(self._P1, "noperm.plugin"):
                raise OSError("You cannot open this file")
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
            mock_listdir.call_args_list, [((self._P1,), {}), ((self._P2,), {})]
        )
        # Ensure that we actually tried to check if things are files
        self.assertEqual(
            mock_isfile.call_args_list,
            [
                ((os.path.join(self._P1, "foo.plugin"),), {}),
                ((os.path.join(self._P1, "bar.plugin"),), {}),
                ((os.path.join(self._P1, "dir.bad.plugin"),), {}),
                ((os.path.join(self._P1, "noperm.plugin"),), {}),
            ],
        )
        # Ensure that we actually tried to open some files
        self.assertEqual(
            mock_open.call_args_list,
            [
                (
                    (os.path.join(self._P1, "bar.plugin"),),
                    {"encoding": "UTF-8"},
                ),
                (
                    (os.path.join(self._P1, "foo.plugin"),),
                    {"encoding": "UTF-8"},
                ),
                (
                    (os.path.join(self._P1, "noperm.plugin"),),
                    {"encoding": "UTF-8"},
                ),
            ],
        )
        # Ensure that an exception was logged
        mock_logger.error.assert_called_with(
            "Unable to load %r: %s",
            "/system/providers/noperm.plugin",
            "You cannot open this file",
        )
        # Ensure that all of the errors are collected
        # Using repr() since OSError seems hard to compare correctly
        self.assertEqual(
            repr(self.col.problem_list[0]),
            repr(OSError("You cannot open this file")),
        )

    @mock.patch("plainbox.impl.secure.plugins.logger")
    @mock.patch("builtins.open")
    @mock.patch("os.path.isfile")
    @mock.patch("os.listdir")
    def test_load__two_extensions(
        self, mock_listdir, mock_isfile, mock_open, mock_logger
    ):
        """
        verify that FsPlugInCollection works with multiple extensions
        """
        mock_listdir.return_value = ["foo.txt", "bar.txt.in"]
        mock_isfile.return_value = True

        def fake_open(path, encoding=None, mode=None):
            m = mock.MagicMock(name="opened file {!r}".format(path))
            m.read.return_value = "text"
            m.__enter__.return_value = m
            return m

        mock_open.side_effect = fake_open
        # Create a collection that looks for both extensions
        col = FsPlugInCollection([self._P1], (".txt", ".txt.in"))
        # Load everything
        col.load()
        # Ensure that we actually tried to look at the filesystem
        self.assertEqual(
            mock_listdir.call_args_list,
            [
                ((self._P1,), {}),
            ],
        )
        # Ensure that we actually tried to check if things are files
        self.assertEqual(
            mock_isfile.call_args_list,
            [
                ((os.path.join(self._P1, "foo.txt"),), {}),
                ((os.path.join(self._P1, "bar.txt.in"),), {}),
            ],
        )
        # Ensure that we actually tried to open some files
        self.assertEqual(
            mock_open.call_args_list,
            [
                (
                    (os.path.join(self._P1, "bar.txt.in"),),
                    {"encoding": "UTF-8"},
                ),
                ((os.path.join(self._P1, "foo.txt"),), {"encoding": "UTF-8"}),
            ],
        )
        # Ensure that no exception was logged
        self.assertEqual(mock_logger.error.mock_calls, [])
        # Ensure that everything was okay
        self.assertEqual(col.problem_list, [])
        # Ensure that both files got added
        self.assertEqual(
            col.get_by_name(os.path.join(self._P1, "foo.txt")).plugin_object,
            "text",
        )
        self.assertEqual(
            col.get_by_name(
                os.path.join(self._P1, "bar.txt.in")
            ).plugin_object,
            "text",
        )
