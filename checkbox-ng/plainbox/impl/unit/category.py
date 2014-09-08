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
:mod:`plainbox.impl.unit.category` -- category unit
===================================================

Categories are a way of associating tests with a human-readable "group".
Particular job definitions can say that they belong to a specific group
(using the category_id field). The display value of that group is loaded
from a particular category unit. This way any provider can extend the list
of categories and we can reliably fix typos and translate the actual names
in a compatible way.
"""

import logging

from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit._legacy import CategoryUnitLegacyAPI
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity

__all__ = ['CategoryUnit']

logger = logging.getLogger("plainbox.unit.category")


class CategoryUnit(UnitWithId, CategoryUnitLegacyAPI):
    """
    Test Category Unit

    This unit defines testing categories. Job definitions can be associated
    with at most one category.
    """

    @classmethod
    def instantiate_template(cls, data, raw_data, origin, provider,
                             parameters, field_offset_map):
        """
        Instantiate this unit from a template.

        The point of this method is to have a fixed API, regardless of what the
        API of a particular unit class ``__init__`` method actually looks like.

        It is easier to standardize on a new method that to patch all of the
        initializers, code using them and tests to have an uniform initializer.
        """
        # This assertion is a low-cost trick to ensure that we override this
        # method in all of the subclasses to ensure that the initializer is
        # called with correctly-ordered arguments.
        assert cls is CategoryUnit, \
            "{}.instantiate_template() not customized".format(cls.__name__)
        return cls(data, raw_data, origin, provider, parameters,
                   field_offset_map)

    def __str__(self):
        """
        same as .name
        """
        return self.name

    def __repr__(self):
        return "<CategoryUnit id:{!r} name:{!r}>".format(self.id, self.name)

    @property
    def name(self):
        """
        Name of the category
        """
        return self.get_record_value('name')

    def tr_name(self):
        """
        Translated name of the category
        """
        return self.get_translated_record_value("name")

    class Meta:

        name = N_('category')

        class fields(SymbolDef):
            """
            Symbols for each field that a JobDefinition can have
            """
            name = 'name'

        field_validators = {
            fields.name: [
                TranslatableFieldValidator,
                TemplateVariantFieldValidator,
                PresentFieldValidator,
                # We want the name to be a single line
                CorrectFieldValueValidator(
                    lambda name: name.count("\n") == 0,
                    Problem.wrong, Severity.warning,
                    message=_("please use only one line"),
                    onlyif=lambda unit: unit.name is not None),
                # We want the name to be relatively short
                CorrectFieldValueValidator(
                    lambda name: len(name) <= 80,
                    Problem.wrong, Severity.warning,
                    message=_("please stay under 80 characters"),
                    onlyif=lambda unit: unit.name is not None),
            ]
        }
