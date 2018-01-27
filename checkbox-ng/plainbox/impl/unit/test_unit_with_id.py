# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.unit.test_unit_with_id
====================================

Test definitions for plainbox.impl.unit.unit_with_id module
"""

from plainbox.impl.unit.test_unit import UnitFieldValidationTests
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import UnitValidationContext
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity


class UnitWithIdFieldValidationTests(UnitFieldValidationTests):

    unit_cls = UnitWithId

    def test_id__untranslatable(self):
        issue_list = self.unit_cls({
            '_id': 'id'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.id,
                              Problem.unexpected_i18n, Severity.warning)

    def test_id__template_variant(self):
        issue_list = self.unit_cls({
            'id': 'id'
        }, parameters={}, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.id,
                              Problem.constant, Severity.error)

    def test_id__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.id,
                              Problem.missing, Severity.error)

    def test_id__unique(self):
        unit = self.unit_cls({
            'id': 'id'
        }, provider=self.provider)
        other_unit = self.unit_cls({
            'id': 'id'
        }, provider=self.provider)
        self.provider.unit_list = [unit, other_unit]
        self.provider.problem_list = []
        context = UnitValidationContext([self.provider])
        message_start = (
            "{} 'id', field 'id', clashes with 1 other unit,"
            " look at: "
        ).format(unit.tr_unit())
        issue_list = unit.check(context=context)
        issue = self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.id,
            Problem.not_unique, Severity.error)
        self.assertTrue(issue.message.startswith(message_start))

    def test_id__without_namespace(self):
        unit = self.unit_cls({
            'id': 'some_ns::id'
        }, provider=self.provider)
        issue_list = unit.check()
        message = (
            "{} 'some_ns::id', field 'id', identifier cannot"
            " define a custom namespace"
        ).format(unit.tr_unit())
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.id,
                              Problem.wrong, Severity.error, message)
