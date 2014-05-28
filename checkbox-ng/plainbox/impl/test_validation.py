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


class ValidationErrorTests(TestCase):

    def test_smoke__no_hint(self):
        err = ValidationError('field', 'problem')
        self.assertEqual(str(err), "Problem with field field: problem")
        self.assertEqual(
            repr(err), "ValidationError(field='field', problem='problem')")

    def test_smoke__hint(self):
        err = ValidationError('field', 'problem', 'hint')
        self.assertEqual(str(err), "Problem with field field: problem")
        self.assertEqual(
            repr(err),
            "ValidationError(field='field', problem='problem', hint='hint')")
