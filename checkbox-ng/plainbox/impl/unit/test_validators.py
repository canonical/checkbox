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
plainbox.impl.unit.test_validators
==================================

Test definitions for plainbox.impl.validators
"""

from textwrap import dedent
from unittest import TestCase
from unittest.mock import MagicMock

from plainbox.impl.unit.validators import (
    CorrectFieldValueValidator,
    DeprecatedFieldValidator,
    IFieldValidator,
    OverrideFieldValueValidator,
    PresentFieldValidator,
    TemplateInvariantFieldValidator,
    TemplateVariantFieldValidator,
    UniqueValueValidator,
    UnitReferenceValidator,
)


class NoTestsForAllThatCode(TestCase):

    def test_fake(self):
        # So that flake8 is silent
        CorrectFieldValueValidator
        DeprecatedFieldValidator
        IFieldValidator
        PresentFieldValidator
        TemplateInvariantFieldValidator
        TemplateVariantFieldValidator
        UniqueValueValidator
        UnitReferenceValidator
        self.assertTrue(True)


class OverrideFieldValueValidatorTests(TestCase):
    def test_check_ok_legacy(self):
        xfail_validators = OverrideFieldValueValidator(["true", "false"])
        parent = MagicMock()
        testplan = MagicMock(xfail_overrides=dedent("""
            apply true to com.canonical.certification::other_id
            apply false to some_id
        """).strip())

        self.assertFalse(
            xfail_validators.check(parent, testplan, "xfail_overrides")
        )

    def test_check_ok_yaml(self):
        xfail_validators = OverrideFieldValueValidator(["true", "false"])
        parent = MagicMock()
        testplan = MagicMock(
            xfail_overrides=[
                "apply true to com.canonical.certification::other_id",
                "apply false to some_id",
            ]
        )

        self.assertFalse(
            xfail_validators.check(parent, testplan, "xfail_overrides")
        )

    def test_check_wrong_value(self):
        xfail_validators = OverrideFieldValueValidator(["true", "false"])
        parent = MagicMock()
        testplan = MagicMock(xfail_overrides=["apply wrong_value to some"])

        self.assertTrue(
            xfail_validators.check(parent, testplan, "xfail_overrides")
        )

    def test_check_wrong_grammar(self):
        xfail_validators = OverrideFieldValueValidator(["true", "false"])
        parent = MagicMock()
        testplan = MagicMock(xfail_overrides=["wrong_value to some"])

        self.assertTrue(
            xfail_validators.check(parent, testplan, "xfail_overrides")
        )
