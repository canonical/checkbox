# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
plainbox.impl.unit.test_file
============================

Test definitions for plainbox.impl.unit.file module
"""

from plainbox.impl.unit.file import FileUnit
from plainbox.impl.unit.file import FileRole
from plainbox.impl.unit.test_unit import UnitFieldValidationTests
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity


class FileUnitFieldValidationTests(UnitFieldValidationTests):

    unit_cls = FileUnit

    def test_path__recommends_pxu(self):
        issue_list = self.unit_cls({
            'unit': self.unit_cls.Meta.name,
            'path': 'foo.txt',
            'role': FileRole.unit_source,
        }, provider=self.provider).check()
        message = ("please use .pxu as an extension for all files with "
                   "plainbox units, see: http://plainbox.readthedocs.org"
                   "/en/latest/author/faq.html#faq-1")
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.path,
                              Problem.deprecated, Severity.advice, message)

    def test_unit__present(self):
        """
        overridden version of UnitFieldValidationTests.test_unit__present()

        This version has a different message and the same semantics as before
        """
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        message = "unit should explicitly define its type"
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.unit,
                              Problem.missing, Severity.advice, message)
