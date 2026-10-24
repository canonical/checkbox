# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

"""Parametric templates instantiated from provider-declared records."""

import json

from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.resource import Resource
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit import concrete_validators
from plainbox.impl.unit.template import TemplateUnit
from plainbox.impl.unit.unit import MissingParam
from plainbox.impl.unit.unit_with_id import UnitWithIdValidator
from plainbox.impl.validation import Problem


class ParametricTemplateValidator(UnitWithIdValidator):
    def check(self, unit):
        yield from super().check(unit)
        for field in unit._data:
            if field.startswith("template-") and (
                field == "template-unit"
                or field not in unit.Meta.field_validators
            ):
                yield self.error(
                    unit,
                    field,
                    Problem.useless,
                    _("parametric template does not support {}").format(field),
                )
        try:
            jobs = unit.instantiate_jobs()
            for job in jobs:
                yield from job.check()
        except MissingParam as exc:
            yield self.error(
                unit,
                exc.field,
                Problem.unknown_param,
                _("reference to unknown parameter {!r}").format(exc.parameter),
            )
        except (ValueError, TypeError, KeyError) as exc:
            yield self.error(
                unit,
                unit.Meta.fields.parameter_records,
                Problem.wrong,
                _("unable to instantiate parametric template: {}").format(exc),
            )


class ParametricTemplateUnit(TemplateUnit):
    """Generate ordinary jobs without running a resource job."""

    @property
    def unit(self):
        return "parametric template"

    @property
    def resource_id(self):
        return None

    @property
    def parameter_records(self):
        records = self.get_record_value("parameters")
        if isinstance(records, str):
            records = json.loads(records)
        return records

    def __str__(self):
        return self.template_id

    def __repr__(self):
        return "<ParametricTemplateUnit template_id:{!r}>".format(
            self.template_id
        )

    def instantiate_jobs(self):
        records = self.parameter_records
        if not isinstance(records, list) or not all(
            isinstance(record, dict) for record in records
        ):
            raise ValueError(_("parameters must be a list of mappings"))
        # Adapt public fields without changing the source or template engine.
        data = {
            key: value
            for key, value in self._data.items()
            if key != "parameters"
            and (not key.startswith("template-") or key == "template-id")
        }
        raw_data = {
            key: value
            for key, value in self._raw_data.items()
            if key != "parameters"
            and (not key.startswith("template-") or key == "template-id")
        }
        data["unit"] = raw_data["unit"] = "template"
        template = TemplateUnit(
            data,
            raw_data=raw_data,
            origin=self.origin,
            provider=self.provider,
            field_offset_map=self.field_offset_map,
        )
        return template.instantiate_all(
            [Resource(record) for record in records]
        )

    class Meta:
        name = N_("parametric template")

        class fields(SymbolDef):
            parameter_records = "parameters"

        validator_cls = ParametricTemplateValidator
        field_validators = {
            TemplateUnit.Meta.fields.template_unit: [],
            TemplateUnit.Meta.fields.template_resource: [
                concrete_validators.absent
            ],
            TemplateUnit.Meta.fields.template_filter: [
                concrete_validators.absent
            ],
            TemplateUnit.Meta.fields.template_imports: [
                concrete_validators.absent
            ],
            fields.parameter_records: [],
        }
