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
plainbox.impl.test_validation
=============================

Test definitions for plainbox.impl.validation module
"""

from unittest import TestCase

from plainbox.impl.validation import ValidationError
from plainbox.impl.validation import Issue
from plainbox.vendor import mock


class ValidationErrorTests(TestCase):

    def test_smoke__no_hint(self):
        err = ValidationError('field', 'problem')
        self.assertEqual(str(err), "Problem with field field: problem")
        self.assertEqual(repr(err), (
            "ValidationError("
            "field='field', problem='problem', hint=None, origin=None)"))

    def test_smoke__hint(self):
        err = ValidationError('field', 'problem', 'hint')
        self.assertEqual(str(err), "Problem with field field: problem")
        self.assertEqual(repr(err), (
            "ValidationError("
            "field='field', problem='problem', hint='hint', origin=None)"))

    def test_smoke__origin(self):
        err = ValidationError('field', 'problem', origin='origin')
        self.assertEqual(str(err), "Problem with field field: problem")
        self.assertEqual(repr(err), (
            "ValidationError("
            "field='field', problem='problem', hint=None, origin='origin')"))


class IssueTests(TestCase):

    def setUp(self):
        self.message = mock.MagicMock(name='message')
        self.severity = mock.MagicMock(name='severity')
        self.kind = mock.MagicMock(name='kind')
        self.origin = mock.MagicMock(name='origin')
        self.issue = Issue(self.message, self.severity, self.kind, self.origin)

    def test_init(self):
        self.assertIs(self.issue.message, self.message)
        self.assertIs(self.issue.severity, self.severity)
        self.assertIs(self.issue.kind, self.kind)
        self.assertIs(self.issue.origin, self.origin)

    def test_str__with_origin(self):
        self.message.__str__.return_value = '<message>'
        self.origin.__str__.return_value = '<origin>'
        self.kind.__str__.return_value = '<kind>'
        self.severity.__str__.return_value = '<severity>'
        self.assertEqual(str(self.issue), "<origin>: <severity>: <message>")

    def test_str__without_origin(self):
        self.issue.origin = None
        self.message.__str__.return_value = '<message>'
        self.kind.__str__.return_value = '<kind>'
        self.severity.__str__.return_value = '<severity>'
        self.assertEqual(str(self.issue), "<severity>: <message>")

    def test_repr__with_origin(self):
        self.message.__repr__ = lambda mock: '(message)'
        self.origin.__repr__ = lambda mock: '(origin)'
        self.kind.__repr__ = lambda mock: '(kind)'
        self.severity.__repr__ = lambda mock: '(severity)'
        self.assertEqual(
            repr(self.issue), (
                'Issue(message=(message), severity=(severity),'
                ' kind=(kind), origin=(origin))'))

    def test_relative_to__with_origin(self):
        path = 'path'
        issue2 = self.issue.relative_to(path)
        self.issue.origin.relative_to.assert_called_with(path)
        self.assertIs(self.issue.message, issue2.message)
        self.assertIs(self.issue.severity, issue2.severity)
        self.assertIs(self.issue.kind, issue2.kind)
        self.assertIs(self.issue.origin.relative_to(path), issue2.origin)

    def test_relative_to__without_origin(self):
        path = 'path'
        self.issue.origin = None
        issue2 = self.issue.relative_to(path)
        self.assertIs(issue2.message, self.issue.message)
        self.assertIs(issue2.severity, self.issue.severity)
        self.assertIs(issue2.kind, self.issue.kind)
        self.assertIs(issue2.origin, None)
