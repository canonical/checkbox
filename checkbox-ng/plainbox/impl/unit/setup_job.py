# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
:mod:`plainbox.impl.unit.setup_job` -- job unit
=========================================
"""

import logging

from plainbox.i18n import gettext as _, gettext_noop as N_
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit import concrete_validators
from plainbox.impl.unit.job import JobDefinition, propertywithsymbols
from plainbox.impl.unit.validators import (
    MemberOfFieldValidator,
)

__all__ = ["SetupJobUnit"]


logger = logging.getLogger("plainbox.unit.setup_job")


class _PluginValues(SymbolDef):
    """
    Symbols for each value of the SetupJobUnit.plugin field
    """

    shell = "shell"


class SetupJobUnit(JobDefinition):
    """
    SetupJob definition class.

    Thin wrapper around the RFC822 record that defines a checkbox setup job
    definition
    """

    def __repr__(self):
        return "<SetupJobUnit id:{!r} plugin:{!r}>".format(
            self.id, self.plugin
        )

    @property
    def unit(self):
        """
        the value of the unit field (overridden)

        The return value is always 'job'
        """
        return "setup_job"

    @propertywithsymbols(symbols=_PluginValues)
    def plugin(self):
        plugin = self.get_record_value("plugin")
        if plugin is None and "simple" in self.get_flag_set():
            plugin = "shell"
        return plugin

    class Meta:

        # this Meta name is job because we are restricting a job but not
        # modifying how Checkbox has to interpret it
        name = N_("job")

        class fields(SymbolDef):
            """
            Symbols for each field that a JobDefinition can have
            """

            name = "name"
            summary = "summary"
            plugin = "plugin"
            command = "command"
            description = "description"
            user = "user"
            environ = "environ"
            estimated_duration = "estimated_duration"
            shell = "shell"
            flags = "flags"
            category_id = "category_id"
            purpose = "purpose"
            steps = "steps"
            verification = "verification"
            certification_status = "certification_status"
            siblings = "siblings"
            auto_retry = "auto_retry"

        field_validators = {
            fields.name: JobDefinition.Meta.field_validators[fields.name],
            fields.summary: JobDefinition.Meta.field_validators[fields.name],
            fields.plugin: [
                concrete_validators.untranslatable,
                concrete_validators.templateInvariant,
                concrete_validators.present,
                MemberOfFieldValidator(_PluginValues.get_all_symbols()),
            ],
            fields.command: JobDefinition.Meta.field_validators[
                fields.command
            ],
            fields.description: JobDefinition.Meta.field_validators[
                fields.description
            ],
            fields.purpose: JobDefinition.Meta.field_validators[
                fields.purpose
            ],
            fields.steps: JobDefinition.Meta.field_validators[fields.steps],
            fields.verification: JobDefinition.Meta.field_validators[
                fields.verification
            ],
            fields.user: JobDefinition.Meta.field_validators[fields.user],
            fields.environ: JobDefinition.Meta.field_validators[
                fields.environ
            ],
            fields.estimated_duration: JobDefinition.Meta.field_validators[
                fields.estimated_duration
            ],
            fields.shell: JobDefinition.Meta.field_validators[fields.shell],
            fields.category_id: JobDefinition.Meta.field_validators[
                fields.category_id
            ],
            fields.flags: JobDefinition.Meta.field_validators[fields.flags],
            fields.certification_status: JobDefinition.Meta.field_validators[
                fields.certification_status
            ],
            fields.siblings: JobDefinition.Meta.field_validators[
                fields.siblings
            ],
            fields.auto_retry: JobDefinition.Meta.field_validators[
                fields.auto_retry
            ],
        }
