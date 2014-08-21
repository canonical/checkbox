# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
plainbox.impl.unit.test_category
================================

Test definitions for plainbox.impl.unit.category module
"""

from unittest import TestCase

from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.unit.category import CategoryUnit
from plainbox.impl.validation import Problem
from plainbox.impl.validation import ValidationError
from plainbox.vendor import mock


class CategoryUnitTests(TestCase):

    def setUp(self):
        self._record = RFC822Record({
            'id': 'id',
            'name': 'name',
        }, Origin(FileTextSource('file.txt'), 1, 2))
        self._gettext_record = RFC822Record({
            '_id': 'id',
            '_name': 'name'
        }, Origin(FileTextSource('file.txt.in'), 1, 2))

    def test_instantiate_template(self):
        data = mock.Mock(name='data')
        raw_data = mock.Mock(name='raw_data')
        origin = mock.Mock(name='origin')
        provider = mock.Mock(name='provider')
        parameters = mock.Mock(name='parameters')
        unit = CategoryUnit.instantiate_template(
            data, raw_data, origin, provider, parameters)
        self.assertIs(unit._data, data)
        self.assertIs(unit._raw_data, raw_data)
        self.assertIs(unit._origin, origin)
        self.assertIs(unit._provider, provider)
        self.assertIs(unit._parameters, parameters)

    def test_smoke_record(self):
        cat = CategoryUnit(self._record.data)
        self.assertEqual(cat.id, "id")
        self.assertEqual(cat.name, "name")

    def test_smoke_gettext_record(self):
        cat = CategoryUnit(self._gettext_record.data)
        self.assertEqual(cat.id, "id")
        self.assertEqual(cat.name, "name")

    def test_str(self):
        cat = CategoryUnit(self._record.data)
        self.assertEqual(str(cat), "name")

    def test_id(self):
        cat = CategoryUnit(self._record.data)
        self.assertEqual(cat.id, "id")

    def test_partial_id(self):
        cat = CategoryUnit(self._record.data)
        self.assertEqual(cat.partial_id, "id")

    def test_repr(self):
        cat = CategoryUnit(self._record.data)
        expected = "<CategoryUnit id:'id' name:'name'>"
        observed = repr(cat)
        self.assertEqual(expected, observed)

    def test_tr_name(self):
        """
        Verify that CategoryUnit.tr_summary() works as expected
        """
        cat = CategoryUnit(self._record.data)
        with mock.patch.object(cat, "get_translated_record_value") as mgtrv:
            retval = cat.tr_name()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with(cat.name)
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_validate(self):
        # NOTE: this test depends on the order of checks in UnitValidator
        # Id is required
        with self.assertRaises(ValidationError) as boom:
            CategoryUnit({}).validate()
        self.assertEqual(boom.exception.problem, Problem.missing)
        self.assertEqual(boom.exception.field, 'id')
        # Name is also required
        with self.assertRaises(ValidationError) as boom:
            CategoryUnit({'id': 'id'}).validate()
        self.assertEqual(boom.exception.problem, Problem.missing)
        self.assertEqual(boom.exception.field, 'name')
        # When both id and name are present, everything is OK
        self.assertIsNone(CategoryUnit({'id': 'id', 'name': 'name'}).validate())