# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
:mod:`plainbox.impl.unit.concrete_validators` -- common validator instances
===========================================================================

This module gathers common validator instances that can be shared among
multiple unit types as their field_validators.
"""

from plainbox.i18n import gettext as _
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity

from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TemplateInvariantFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator


translatable = TranslatableFieldValidator()
templateVariant = TemplateVariantFieldValidator()
templateInvariant = TemplateInvariantFieldValidator()
untranslatable = UntranslatableFieldValidator()
present = PresentFieldValidator()

localDeprecated = CorrectFieldValueValidator(
    lambda plugin: plugin != 'local', Problem.deprecated, Severity.advice,
    message=_("please migrate to job templates, see plainbox-template-unit(7)"
              " for details"))

oneLine = CorrectFieldValueValidator(
    lambda field: field is not None and field.count("\n") == 0,
    Problem.wrong, Severity.warning,
    message=_("please use only one line"))

shortValue = CorrectFieldValueValidator(
    lambda field: field is not None and len(field) <= 80,
    Problem.wrong, Severity.warning,
    message=_("please stay under 80 characters"))
