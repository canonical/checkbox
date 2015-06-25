# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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
plainbox.impl.unit.test_exporter
================================

Test definitions for plainbox.impl.unit.exporter module
"""

from unittest import TestCase
import warnings

from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.unit.exporter import ExporterUnit
from plainbox.impl.unit.exporter import ExporterUnitSupport
from plainbox.impl.unit.test_unit_with_id import UnitWithIdFieldValidationTests
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity
from plainbox.impl.validation import ValidationError
from plainbox.vendor import mock


class ExporterUnitTests(TestCase):

    def setUp(self):
        self._record = RFC822Record({
            'id': 'id',
            'unit': 'exporter',
            '_summary': 'summary',
            'entry_point': 'text',
            'file_extension': 'file_extension',
        }, Origin(FileTextSource('file.txt'), 1, 2))
        warnings.filterwarnings(
            'ignore', 'validate is deprecated since version 0.11')

    def tearDown(self):
        warnings.resetwarnings()

    def test_smoke_record(self):
        exp = ExporterUnit(self._record.data)
        self.assertEqual(exp.id, "id")
        self.assertEqual(exp.summary, "summary")

    def test_str(self):
        exp = ExporterUnit(self._record.data)
        self.assertEqual(str(exp), "summary")

    def test_id(self):
        exp = ExporterUnit(self._record.data)
        self.assertEqual(exp.id, "id")

    def test_partial_id(self):
        exp = ExporterUnit(self._record.data)
        self.assertEqual(exp.partial_id, "id")

    def test_repr(self):
        exp = ExporterUnit(self._record.data)
        expected = "<ExporterUnit id:'id' entry_point:'text'>"
        observed = repr(exp)
        self.assertEqual(expected, observed)

    def test_tr_summary(self):
        """Verify that ExporterUnit.tr_summary() works as expected."""
        exp = ExporterUnit(self._record.data)
        with mock.patch.object(exp, "get_translated_record_value") as mgtrv:
            retval = exp.tr_summary()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with(exp.summary, '')
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_options(self):
        exp = mock.Mock(spec_set=ExporterUnit)
        exp.data = "{}"
        exp.entry_point = 'text'
        exp.options = 'a bc de=f, g ;h, ij-k\nlm=nop , q_r'
        exp.check.return_value = False
        sup = ExporterUnitSupport(exp)
        self.assertEqual(
            sup.option_list,
            ['a', 'bc', 'de=f', 'g', 'h', 'ij-k', 'lm=nop', 'q_r'])

    def test_validate(self):
        # NOTE: this test depends on the order of checks in UnitValidator
        # Id is required
        with self.assertRaises(ValidationError) as boom:
            ExporterUnit({}).validate()
        self.assertEqual(boom.exception.problem, Problem.missing)
        self.assertEqual(boom.exception.field, 'id')
        # When both id, file_extension and entry_point are present, everything
        # is OK
        self.assertIsNone(ExporterUnit({
            'id': 'id', 'entry_point': 'entry_point',
            'file_extension': 'file_extension'
        }).validate())


class ExporterUnitFieldValidationTests(UnitWithIdFieldValidationTests):

    unit_cls = ExporterUnit

    def a_test_summary__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.summary,
                              Problem.missing, Severity.advice)

    def test_summary__translatable(self):
        issue_list = self.unit_cls({
            'summary': 'summary'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.summary,
                              Problem.expected_i18n, Severity.warning)

    def test_entry_point__untranslatable(self):
        issue_list = self.unit_cls({
            '_entry_point': 'entry_point'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.entry_point,
            Problem.unexpected_i18n, Severity.warning)

    def test_file_extension__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list,
                              self.unit_cls.Meta.fields.file_extension,
                              Problem.missing, Severity.error)

    def test_file_extension__untranslatable(self):
        issue_list = self.unit_cls({
            '_file_extension': 'file_extension'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.file_extension,
            Problem.unexpected_i18n, Severity.warning)

    def test_entry_point__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list,
                              self.unit_cls.Meta.fields.entry_point,
                              Problem.missing, Severity.error)

    def test_data__untranslatable(self):
        issue_list = self.unit_cls({
            '_data': '{"foo": "bar"}'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.data,
            Problem.unexpected_i18n, Severity.warning)

    def test_data__json_content(self):
        issue_list = self.unit_cls({
            'data': 'junk'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.data,
            Problem.syntax_error, Severity.error)
