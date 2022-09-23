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

from unittest import TestCase

from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import DeprecatedFieldValidator
from plainbox.impl.unit.validators import IFieldValidator
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TemplateInvariantFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.unit.validators import UniqueValueValidator
from plainbox.impl.unit.validators import UnitReferenceValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator


class NoTestsForAllThatCode(TestCase):

    def test_fake(self):
        # So that flake8 is silent
        CorrectFieldValueValidator
        DeprecatedFieldValidator
        IFieldValidator
        PresentFieldValidator
        TemplateInvariantFieldValidator
        TemplateVariantFieldValidator
        TranslatableFieldValidator
        UniqueValueValidator
        UnitReferenceValidator
        UntranslatableFieldValidator
        self.assertTrue(True)
