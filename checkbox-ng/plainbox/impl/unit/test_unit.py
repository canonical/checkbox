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
import warnings

from plainbox.abc import IProvider1
from plainbox.impl.unit.unit import Unit
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity
from plainbox.impl.validation import ValidationError
from plainbox.vendor import mock


def setUpModule():
    warnings.filterwarnings(
        'ignore', 'validate is deprecated since version 0.11')


def tearDownModule():
    warnings.resetwarnings()


class IssueMixIn:
    """
    Mix in for TestCase to work with issues and issue lists
    """

    def assertIssueFound(self, issue_list, field=None, kind=None,
                         severity=None, message=None):
        """
        Raise an assertion unless an issue with the required fields is found

        :param issue_list:
            A list of issues to look through
        :param field:
            (optional) value that must match the same attribute on the Issue
        :param kind:
            (optional) value that must match the same attribute on the Issue
        :param severity:
            (optional) value that must match the same attribute on the Issue
        :param message:
            (optional) value that must match the same attribute on the Issue
        :returns:
            The issue matching those constraints, if found
        """
        for issue in issue_list:
            if field is not None and issue.field is not field:
                continue
            if severity is not None and issue.severity is not severity:
                continue
            if kind is not None and issue.kind is not kind:
                continue
            if message is not None and issue.message != message:
                continue
            return issue
        else:
            msg = "no issue matching:\n{}\nwas found in:\n{}".format(
                '\n'.join(
                    ' * {} is {!r}'.format(issue_attr, value)
                    for issue_attr, value in
                    [('field', field),
                     ('severity', severity),
                     ('kind', kind),
                     ('message', message)]
                    if value is not None),
                '\n'.join(" - {!r}".format(issue) for issue in issue_list))
            return self.fail(msg)


class TestUnitDefinition(TestCase):

    def test_instantiate_template(self):
        data = mock.Mock(name='data')
        raw_data = mock.Mock(name='raw_data')
        origin = mock.Mock(name='origin')
        provider = mock.Mock(name='provider')
        parameters = mock.Mock(name='parameters')
        field_offset_map = mock.Mock(name='field_offset_map')
        unit = Unit.instantiate_template(
            data, raw_data, origin, provider, parameters, field_offset_map)
        self.assertIs(unit._data, data)
        self.assertIs(unit._raw_data, raw_data)
        self.assertIs(unit._origin, origin)
        self.assertIs(unit._provider, provider)
        self.assertIs(unit._parameters, parameters)
        self.assertIs(unit._field_offset_map, field_offset_map)

    def test_get_raw_record_value(self):
        """
        Ensure that get_raw_record_value() works okay
        """
        unit1 = Unit({'key': 'value'}, {'key': 'raw-value'})
        unit2 = Unit({'_key': 'value'}, {'_key': 'raw-value'})
        unit3 = Unit({'key': '{param}'}, {'key': 'raw-{param}'},
                     parameters={'param': 'value'})
        unit4 = Unit({'key': '{missing_param}'},
                     {'key': 'raw-{missing_param}'},
                     parameters={'param': 'value'})
        unit5 = Unit({})
        unit6 = Unit({}, parameters={'param': 'value'})
        self.assertEqual(unit1.get_raw_record_value('key'), 'raw-value')
        self.assertEqual(unit2.get_raw_record_value('key'), 'raw-value')
        self.assertEqual(unit3.get_raw_record_value('key'), 'raw-value')
        with self.assertRaises(KeyError):
            unit4.get_raw_record_value('key')
        self.assertEqual(unit5.get_raw_record_value('key'), None)
        self.assertEqual(
            unit5.get_raw_record_value('key', 'default'), 'default')
        self.assertEqual(unit6.get_raw_record_value('key'), None)
        self.assertEqual(
            unit6.get_raw_record_value('key', 'default'), 'default')

    def test_get_record_value(self):
        """
        Ensure that get_record_value() works okay
        """
        unit1 = Unit({'key': 'value'}, {'key': 'raw-value'})
        unit2 = Unit({'_key': 'value'}, {'_key': 'raw-value'})
        unit3 = Unit({'key': '{param}'}, {'key': 'raw-{param}'},
                     parameters={'param': 'value'})
        unit4 = Unit({'key': '{missing_param}'},
                     {'key': 'raw-{missing_param}'},
                     parameters={'param': 'value'})
        unit5 = Unit({})
        unit6 = Unit({}, parameters={'param': 'value'})
        self.assertEqual(unit1.get_record_value('key'), 'value')
        self.assertEqual(unit2.get_record_value('key'), 'value')
        self.assertEqual(unit3.get_record_value('key'), 'value')
        with self.assertRaises(KeyError):
            unit4.get_record_value('key')
        self.assertEqual(unit5.get_record_value('key'), None)
        self.assertEqual(unit5.get_record_value('key', 'default'), 'default')
        self.assertEqual(unit6.get_record_value('key'), None)
        self.assertEqual(unit6.get_record_value('key', 'default'), 'default')

    def test_validate(self):
        # Empty units are valid, with or without parameters
        Unit({}).validate()
        Unit({}, parameters={}).validate()
        # Fields cannot refer to parameters that are not supplied
        with self.assertRaises(ValidationError) as boom:
            Unit({'field': '{param}'}, parameters={}).validate()
        self.assertEqual(boom.exception.field, 'field')
        self.assertEqual(boom.exception.problem, Problem.wrong)
        # Fields must obey template constraints. (id: vary)
        with self.assertRaises(ValidationError) as boom:
            UnitWithId({'id': 'a-simple-id'}, parameters={}).validate()
        self.assertEqual(boom.exception.field, 'id')
        self.assertEqual(boom.exception.problem, Problem.constant)
        # Fields must obey template constraints. (unit: const)
        with self.assertRaises(ValidationError) as boom:
            Unit({'unit': '{parametric_id}'},
                 parameters={'parametric_id': 'foo'}).validate()
        self.assertEqual(boom.exception.field, 'unit')
        self.assertEqual(boom.exception.problem, Problem.variable)

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

    @mock.patch('plainbox.impl.unit.unit.normalize_rfc822_value')
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

    @mock.patch('plainbox.impl.unit.unit.normalize_rfc822_value')
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

    def test_checksum_smoke(self):
        unit1 = Unit({'plugin': 'plugin', 'user': 'root'})
        identical_to_unit1 = Unit({'plugin': 'plugin', 'user': 'root'})
        # Two distinct but identical units have the same checksum
        self.assertEqual(unit1.checksum, identical_to_unit1.checksum)
        unit2 = Unit({'plugin': 'plugin', 'user': 'anonymous'})
        # Two units with different definitions have different checksum
        self.assertNotEqual(unit1.checksum, unit2.checksum)
        # The checksum is stable and does not change over time
        self.assertEqual(
            unit1.checksum,
            "c47cc3719061e4df0010d061e6f20d3d046071fd467d02d093a03068d2f33400")
        unit3 = Unit({'plugin': 'plugin', 'user': 'anonymous'},
                     parameters={'param': 'value'})
        # Units with identical data but different parameters have different
        # checksums
        self.assertNotEqual(unit2.checksum, unit3.checksum)
        # The checksum is stable and does not change over time
        self.assertEqual(
            unit3.checksum,
            "5558e5231fb192e8126ed69d950972fa878375d1364a221ed6550852e7d5cde0")

    def test_comparison(self):
        # Ensure that units with equal data are equal
        self.assertEqual(Unit({}), Unit({}))
        # Ensure that units with equal data and equal parameters are equal
        self.assertEqual(
            Unit({}, parameters={'param': 'value'}),
            Unit({}, parameters={'param': 'value'}))
        # Ensure that units with equal data but different origin are still
        # equal
        self.assertEqual(
            Unit({}, origin=mock.Mock()),
            Unit({}, origin=mock.Mock()))
        # Ensure that units with equal data but different provider are still
        # equal
        self.assertEqual(
            Unit({}, provider=mock.Mock()),
            Unit({}, provider=mock.Mock()))
        # Ensure that units with equal data but different raw data are still
        # equal
        self.assertEqual(
            Unit({}, raw_data={'key': 'raw-value-1'}),
            Unit({}, raw_data={'key': 'raw-value-2'}))
        # Ensure that units with different data are not equal
        self.assertNotEqual(
            Unit({'key': 'value'}), Unit({'key': 'other-value'}))
        # Ensure that units with equal data but different parameters are not
        # equal
        self.assertNotEqual(
            Unit({}, parameters={'param': 'value1'}),
            Unit({}, parameters={'param': 'value2'}))
        # Ensure that units are not equal to other classes
        self.assertTrue(Unit({}) != object())
        self.assertFalse(Unit({}) == object())

    def test_get_accessed_parameters(self):
        # There are no accessed parameters if the unit is not parameterized
        self.assertEqual(
            Unit({}).get_accessed_parameters(), {})
        self.assertEqual(
            Unit({'field': 'value'}).get_accessed_parameters(),
            {'field': frozenset()})
        self.assertEqual(
            Unit({'field': '{param}'}).get_accessed_parameters(),
            {'field': frozenset()})
        # As soon as we enable parameters we get them exposed
        self.assertEqual(
            Unit({}, parameters={'param': 'value'}).get_accessed_parameters(),
            {})
        self.assertEqual(
            Unit({
                'field': 'value'}, parameters={'param': 'value'}
            ).get_accessed_parameters(), {'field': frozenset()})
        self.assertEqual(
            Unit({
                'field': '{param}'}, parameters={'param': 'value'}
            ).get_accessed_parameters(), {'field': frozenset(['param'])})
        # We can always use force=True to pretend any unit is parametric
        self.assertEqual(Unit({}).get_accessed_parameters(force=True), {})
        self.assertEqual(
            Unit({'field': 'value'}).get_accessed_parameters(force=True),
            {'field': frozenset()})
        self.assertEqual(
            Unit({'field': '{param}'}).get_accessed_parameters(force=True),
            {'field': frozenset(['param'])})

    def test_qualify_id__with_provider(self):
        provider = mock.Mock(spec_set=IProvider1)
        provider.namespace = 'ns'
        unit = Unit({}, provider=provider)
        self.assertEqual(unit.qualify_id('id'), 'ns::id')
        self.assertEqual(unit.qualify_id('some-ns::id'), 'some-ns::id')

    def test_qualify_id__without_provider(self):
        unit = Unit({})
        self.assertEqual(unit.qualify_id('id'), 'id')
        self.assertEqual(unit.qualify_id('some-ns::id'), 'some-ns::id')


class UnitFieldValidationTests(TestCase, IssueMixIn):

    unit_cls = Unit

    def setUp(self):
        self.provider = mock.Mock(spec_set=IProvider1)
        self.provider.namespace = 'ns'

    def test_unit__untranslatable(self):
        issue_list = self.unit_cls({
            '_unit': 'unit'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.unit,
                              Problem.unexpected_i18n, Severity.warning)

    def test_unit__template_invariant(self):
        issue_list = self.unit_cls({
            'unit': '{attr}'
        }, parameters={'attr': 'unit'}, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.unit,
                              Problem.variable, Severity.error)

    def test_unit__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        message = "field 'unit', unit should explicitly define its type"
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.unit,
                              Problem.missing, Severity.advice, message)
