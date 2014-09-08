# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.unit_with_id` -- unit with identifier definition
====================================================================
"""

import logging

from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit._legacy import UnitWithIdLegacyAPI
from plainbox.impl.unit._legacy import UnitWithIdValidatorLegacyAPI
from plainbox.impl.unit.unit import Unit
from plainbox.impl.unit.unit import UnitValidator
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import UniqueValueValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator

__all__ = ['UnitWithId']


logger = logging.getLogger("plainbox.unit.unit_with_id")


class UnitWithIdValidator(UnitValidator, UnitWithIdValidatorLegacyAPI):
    """
    Validator for :class:`UnitWithId`
    """

    def explain(self, unit, field, kind, message):
        """
        Lookup an explanatory string for a given issue kind

        :returns:
            A string (explanation) or None if the issue kind
            is not known to this method.

        This version overrides the base implementation to use the unit id, if
        it is available, when reporting issues. This makes the error message
        easier to read for the vast majority of current units (jobs) that have
        an identifier and are commonly addressed with one by developers.
        """
        if unit.partial_id is None:
            return super().explain(unit, field, kind, message)
        stock_msg = self._explain_map.get(kind)
        if stock_msg is None:
            return None
        return _("{unit} {id!a}, field {field!a}, {message}").format(
            unit=unit.tr_unit(), id=unit.partial_id, field=str(field),
            message=message or stock_msg)


class UnitWithId(Unit, UnitWithIdLegacyAPI):
    """
    Base class for Units that have unique identifiers

    Unlike the JobDefintion class the partial_id property has no fallback
    and is simply tied directly to the "id" field. The id property works
    in conjunction with a provider associated with the unit and simply adds
    the namespace part.
    """

    @property
    def partial_id(self):
        """
        Identifier of this unit, without the provider namespace
        """
        return self.get_record_value('id')

    @property
    def id(self):
        """
        Identifier of this unit, with the provider namespace.

        .. note::
            In rare (unit tests only?) edge case a Unit can be separated
            from the parent provider. In that case the value of ``id`` is
            always equal to ``partial_id``.
        """
        if self.provider and self.partial_id:
            return "{}::{}".format(self.provider.namespace, self.partial_id)
        else:
            return self.partial_id

    class Meta:

        name = N_('unit-with-id')

        class fields(SymbolDef):
            id = 'id'

        validator_cls = UnitWithIdValidator

        field_validators = {
            fields.id: [
                # We don't want anyone marking id up for translation
                UntranslatableFieldValidator,
                # We want this field to be present at all times
                PresentFieldValidator,
                # We want each instance to have a different identifier
                TemplateVariantFieldValidator,
                # When checking in a globally, all units need an unique value
                UniqueValueValidator,
                # We want to have bare, namespace-less identifiers
                CorrectFieldValueValidator(
                    lambda value, unit: (
                        "::" not in unit.get_record_value('id')),
                    message=_("identifier cannot define a custom namespace"),
                    onlyif=lambda unit: unit.get_record_value('id')),
            ]
        }
