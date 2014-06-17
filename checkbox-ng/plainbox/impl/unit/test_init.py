# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.unit.test_init
============================

Test definitions for plainbox.impl.unit (package init file)
"""

from unittest import TestCase

from plainbox.impl.unit import Unit
from plainbox.vendor import mock


class TestUnitDefinition(TestCase):

    def test_get_raw_record_value(self):
        """
        Ensure that get_raw_record_value() works okay
        """
        unit1 = Unit({'key': 'value'}, {'key': 'raw-value'})
        unit2 = Unit({'_key': 'value'}, {'_key': 'raw-value'})
        self.assertEqual(unit1.get_raw_record_value('key'), 'raw-value')
        self.assertEqual(unit2.get_raw_record_value('key'), 'raw-value')

    def test_get_record_value(self):
        """
        Ensure that get_record_value() works okay
        """
        unit1 = Unit({'key': 'value'}, {'key': 'raw-value'})
        unit2 = Unit({'_key': 'value'}, {'_key': 'raw-value'})
        self.assertEqual(unit1.get_record_value('key'), 'value')
        self.assertEqual(unit2.get_record_value('key'), 'value')

    def test_validate(self):
        unit = Unit({})
        unit.validate()

    def test_get_translated_data__typical(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        unit = Unit({})
        with mock.patch.object(unit, "_provider") as mock_provider:
            retval = unit.get_translated_data('foo')
        mock_provider.get_translated_data.assert_called_with("foo")
        self.assertEqual(retval, mock_provider.get_translated_data())

    def test_get_translated_data__no_provider(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        unit = Unit({})
        unit._provider = None
        self.assertEqual(unit.get_translated_data('foo'), 'foo')

    def test_get_translated_data__empty_msgid(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        unit = Unit({})
        with mock.patch.object(unit, "_provider"):
            self.assertEqual(unit.get_translated_data(''), '')

    def test_get_translated_data__None_msgid(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        unit = Unit({})
        with mock.patch.object(unit, "_provider"):
            self.assertEqual(unit.get_translated_data(None), None)

    @mock.patch('plainbox.impl.unit.normalize_rfc822_value')
    def test_get_normalized_translated_data__typical(self, mock_norm):
        """
        verify the runtime behavior of get_normalized_translated_data()
        """
        unit = Unit({})
        with mock.patch.object(unit, "get_translated_data") as mock_tr:
            retval = unit.get_normalized_translated_data('foo')
        # get_translated_data('foo') was called
        mock_tr.assert_called_with("foo")
        # normalize_rfc822_value(x) was called
        mock_norm.assert_called_with(mock_tr())
        # return value was returned
        self.assertEqual(retval, mock_norm())

    @mock.patch('plainbox.impl.unit.normalize_rfc822_value')
    def test_get_normalized_translated_data__no_translation(self, mock_norm):
        """
        verify the runtime behavior of get_normalized_translated_data()
        """
        unit = Unit({})
        with mock.patch.object(unit, "get_translated_data") as mock_tr:
            mock_tr.return_value = None
            retval = unit.get_normalized_translated_data('foo')
        # get_translated_data('foo') was called
        mock_tr.assert_called_with("foo")
        # normalize_rfc822_value(x) was NOT called
        self.assertEqual(mock_norm.call_count, 0)
        # return value was returned
        self.assertEqual(retval, 'foo')
