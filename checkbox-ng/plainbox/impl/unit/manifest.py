# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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

""" Manifest Entry Unit. """
import logging

from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator

logger = logging.getLogger("plainbox.unit.manifest")


__all__ = ('ManifestEntryUnit', )


class ManifestEntryUnit(UnitWithId):

    """
    Unit representing a single entry in a hardware specification manifest.

    This unit can be used to describe a single quality (either qualitative or
    quantitative) of a device under test. Manifest data is provided externally
    and cannot or should not be detected by the code running on the device.
    """

    @property
    def name(self):
        """ Name of the entry. """
        return self.get_record_value('name')

    def tr_name(self):
        """ Name of the entry (translated). """
        return self.get_translated_record_value('name')

    @property
    def value_type(self):
        """
        Type of value of the entry.

        This field defines the kind of entry we wish to describe. Currently
        only ``"natural"`` and ``"bool"`` are supported. This value is loaded
        from the ``value-type`` field.
        """
        return self.get_record_value('value-type')

    @property
    def value_unit(self):
        """
        Type of unit the value is measured in.

        Typically this will be the unit in which the quantity is measured, e.g.
        "Mbit", "GB". This value is loaded from the ``value-unit`` field.
        """
        return self.get_record_value('value-unit')

    @property
    def resource_key(self):
        """
        Name of this manifest entry when presented as a resource.

        This value is loaded from the ``resource-key`` field. It defaults to
        the partial identifier of the unit.
        """
        return self.get_record_value('resource-key', self.partial_id)

    class Meta:

        name = 'manifest entry'

        class fields(SymbolDef):

            """ Symbols for each field that a TestPlan can have. """

            name = 'name'
            value_type = 'value-type'
            value_unit = 'value-unit'
            resource_key = 'resource-key'

        field_validators = {
            fields.name: [
                TranslatableFieldValidator,
                TemplateVariantFieldValidator,
                PresentFieldValidator,
            ],
            fields.value_type: [
                UntranslatableFieldValidator,
                PresentFieldValidator(),
                CorrectFieldValueValidator(
                    lambda value_type: value_type in ('bool', 'natural')),
            ],
            fields.value_unit: [
                # OPTIONAL
            ],
            fields.resource_key: [
                UntranslatableFieldValidator,
            ]
        }
