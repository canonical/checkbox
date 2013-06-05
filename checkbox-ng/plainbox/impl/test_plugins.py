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

import mock

from plainbox.impl.plugins import IPlugIn, PlugIn, PlugInCollection


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


class PlugInCollectionTests(TestCase):

    _NAMESPACE = "namespace"

    def test_smoke(self):
        # Create a collection
        col = PlugInCollection(self._NAMESPACE)
        # Ensure that namespace was saved
        self.assertEqual(col._namespace, self._NAMESPACE)
        # Ensure that plugins start out empty
        self.assertEqual(len(col._plugins), 0)
        # Ensure that 'loaded' flag is false
        self.assertFalse(col._loaded)

    def test_default_wrapper(self):
        # Create a collection
        col = PlugInCollection(self._NAMESPACE)
        # Ensure that the wrapper is :class:`PlugIn`
        self.assertEqual(col._wrapper, PlugIn)

    @mock.patch('pkg_resources.iter_entry_points')
    def test_load(self, mock_iter):
        # Create a collection
        col = PlugInCollection(self._NAMESPACE)
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
        col.load()
        # Ensure that pkg_resources were interrogated
        mock_iter.assert_calledwith(self._NAMESPACE)
        # Ensure that both entry points were loaded
        mock_ep1.load.assert_called_with()
        mock_ep2.load.assert_called_with()

    @mock.patch('plainbox.impl.plugins.logger')
    @mock.patch('pkg_resources.iter_entry_points')
    def test_load_failing(self, mock_iter, mock_logger):
        # Create a collection
        col = PlugInCollection(self._NAMESPACE)
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
        col.load()
        # Ensure that pkg_resources were interrogated
        mock_iter.assert_calledwith(self._NAMESPACE)
        # Ensure that both entry points were loaded
        mock_ep1.load.assert_called_with()
        mock_ep2.load.assert_called_with()
        # Ensure that an exception was logged
        mock_logger.exception.assert_called_with(
            "Unable to import %s", mock_ep2)

    def test_aux_methods(self):
        # Create a collection
        col = PlugInCollection(self._NAMESPACE)
        # Create a mocked entry plugin
        plug1 = PlugIn("ep1", "obj1")
        plug2 = PlugIn("ep2", "obj2")
        # With fake plugins
        with col.fake_plugins([plug1, plug2]):
            # Check that plugins are correct
            self.assertIs(col.get_by_name('ep1'), plug1)
            self.assertIs(col.get_by_name('ep2'), plug2)
            # Access all plugins
            self.assertEqual(col.get_all_plugins(), [plug1, plug2])
            # Access all plugin names
            self.assertEqual(col.get_all_names(), ['ep1', 'ep2'])
            # Access all pairs (name, plugin)
            self.assertEqual(col.get_all_items(),
                             [('ep1', plug1), ('ep2', plug2)])
