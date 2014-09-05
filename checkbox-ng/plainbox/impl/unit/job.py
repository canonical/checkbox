# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.impl.unit.job` -- job unit
=========================================
"""

import logging
import re

from plainbox.abc import IJobDefinition
from plainbox.i18n import gettext as _
from plainbox.impl.resource import ResourceProgram
from plainbox.impl.resource import parse_imports_stmt
from plainbox.impl.secure.origin import JobOutputTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit._legacy import JobDefinitionLegacyAPI
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import DeprecatedFieldValidator
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import ReferenceConstraint
from plainbox.impl.unit.validators import ShellProgramValidator
from plainbox.impl.unit.validators import TemplateInvariantFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.unit.validators import UnitReferenceValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator
from plainbox.impl.unit.validators import UselessFieldValidator
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity

__all__ = ['JobDefinition', 'propertywithsymbols']


logger = logging.getLogger("plainbox.unit.job")


class propertywithsymbols(property):
    """
    A property that also keeps a group of symbols around
    """

    def __init__(self, fget=None, fset=None, fdel=None, doc=None,
                 symbols=None):
        """
        Initializes the property with the specified values
        """
        super(propertywithsymbols, self).__init__(fget, fset, fdel, doc)
        self.__doc__ = doc
        self.symbols = symbols

    def __getattr__(self, attr):
        """
        Internal implementation detail.

        Exposes all of the attributes of the SymbolDef group as attributes of
        the property. The way __getattr__() works it can never hide any
        existing attributes so it is safe not to break the property.
        """
        return getattr(self.symbols, attr)

    def __call__(self, fget):
        """
        Internal implementation detail.

        Used to construct the decorator with fget defined to the decorated
        function.
        """
        return propertywithsymbols(
            fget, self.fset, self.fdel, self.__doc__, symbols=self.symbols)


class _PluginValues(SymbolDef):
    """
    Symbols for each value of the JobDefinition.plugin field
    """
    attachment = 'attachment'
    local = 'local'
    resource = 'resource'
    manual = 'manual'
    user_verify = "user-verify"
    user_interact = "user-interact"
    user_interact_verify = "user-interact-verify"
    shell = 'shell'


class JobDefinition(UnitWithId, JobDefinitionLegacyAPI, IJobDefinition):
    """
    Job definition class.

    Thin wrapper around the RFC822 record that defines a checkbox job
    definition
    """

    def __init__(self, data, origin=None, provider=None, controller=None,
                 raw_data=None, parameters=None, field_offset_map=None):
        """
        Initialize a new JobDefinition instance.

        :param data:
            Normalized data that makes up this job definition
        :param origin:
            An (optional) Origin object. If omitted a fake origin object is
            created. Normally the origin object should be obtained from the
            RFC822Record object.
        :param provider:
            An (optional) Provider1 object. If omitted it defaults to None but
            the actual job definition is not suitable for execution. All job
            definitions are expected to have a provider.
        :param controller:
            An (optional) session state controller. If omitted a checkbox
            session state controller is implicitly used. The controller defines
            how this job influences the session it executes in.
        :param raw_data:
            An (optional) raw version of data, without whitespace
            normalization. If omitted then raw_data is assumed to be data.
        :param parameters:
            An (optional) dictionary of parameters. Parameters allow for unit
            properties to be altered while maintaining a single definition.
            This is required to obtain translated summary and description
            fields, while having a single translated base text and any
            variation in the available parameters.
        :param field_offset_map:
            An optional dictionary with offsets (in line numbers) of each
            field.  Line numbers are relative to the value of origin.line_start

        .. note::
            You should almost always use :meth:`from_rfc822_record()` instead.
        """
        if origin is None:
            origin = Origin.get_caller_origin()
        super().__init__(data, raw_data=raw_data, origin=origin,
                         provider=provider, parameters=parameters,
                         field_offset_map=field_offset_map)
        # NOTE: controllers cannot be customized for instantiated templates so
        # I wonder if we should start hard-coding it in. Nothing seems to be
        # using custom controller functionality anymore.
        if controller is None:
            # XXX: moved here because of cyclic imports
            from plainbox.impl.ctrl import checkbox_session_state_ctrl
            controller = checkbox_session_state_ctrl
        self._resource_program = None
        self._controller = controller

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
        assert cls is JobDefinition, \
            "{}.instantiate_template() not customized".format(cls.__name__)
        return cls(data, origin, provider, None, raw_data, parameters,
                   field_offset_map)

    def __str__(self):
        return self.summary

    def __repr__(self):
        return "<JobDefinition id:{!r} plugin:{!r}>".format(
            self.id, self.plugin)

    @property
    def unit(self):
        """
        the value of the unit field (overridden)

        The return value is always 'job'
        """
        return 'job'

    def tr_unit(self):
        """
        Translated (optionally) value of the unit field (overridden)

        The return value is always 'job' (translated)
        """
        return _("job")

    @property
    def partial_id(self):
        """
        Identifier of this job, without the provider name

        This field should not be used anymore, except for display
        """
        return self.get_record_value('id', self.get_record_value('name'))

    @propertywithsymbols(symbols=_PluginValues)
    def plugin(self):
        return self.get_record_value('plugin')

    @property
    def summary(self):
        return self.get_record_value('summary', self.partial_id)

    @property
    def description(self):
        return self.get_record_value('description')

    @property
    def requires(self):
        return self.get_record_value('requires')

    @property
    def depends(self):
        return self.get_record_value('depends')

    @property
    def command(self):
        return self.get_record_value('command')

    @property
    def environ(self):
        return self.get_record_value('environ')

    @property
    def user(self):
        return self.get_record_value('user')

    @property
    def flags(self):
        return self.get_record_value('flags')

    @property
    def shell(self):
        """
        Shell that is used to interpret the command

        Defaults to 'bash' for checkbox compatibility.
        """
        return self.get_record_value('shell', 'bash')

    @property
    def imports(self):
        return self.get_record_value('imports')

    @property
    def category_id(self):
        return self.get_record_value('category_id')

    @property
    def estimated_duration(self):
        """
        estimated duration of this job in seconds.

        The value may be None, which indicates that the duration is basically
        unknown. Fractional numbers are allowed and indicate fractions of a
        second.
        """
        value = self.get_record_value('estimated_duration')
        if value is not None:
            try:
                return float(value)
            except ValueError:
                pass

    @property
    def controller(self):
        """
        The controller object associated with this JobDefinition
        """
        return self._controller

    def tr_summary(self):
        """
        Get the translated version of :meth:`summary`
        """
        return self.get_translated_record_value('summary', self.partial_id)

    def tr_description(self):
        """
        Get the translated version of :meth:`description`
        """
        return self.get_translated_record_value('description')

    def get_environ_settings(self):
        """
        Return a set of requested environment variables
        """
        if self.environ is not None:
            return {variable for variable in re.split('[\s,]+', self.environ)}
        else:
            return set()

    def get_flag_set(self):
        """
        Return a set of flags associated with this job
        """
        if self.flags is not None:
            return {flag for flag in re.split('[\s,]+', self.flags)}
        else:
            return set()

    def get_imported_jobs(self):
        """
        Parse the 'imports' line and compute the imported symbols.

        Return generator for a sequence of pairs (job_id, identifier) that
        describe the imported job identifiers from arbitrary namespace.

        The syntax of each imports line is:

        IMPORT_STMT ::  "from" <NAMESPACE> "import" <PARTIAL_ID>
                      | "from" <NAMESPACE> "import" <PARTIAL_ID>
                         AS <IDENTIFIER>
        """
        imports = self.imports or ""
        return parse_imports_stmt(imports)

    @property
    def automated(self):
        """
        Whether the job is fully automated and runs without any
        intervention from the user
        """
        return self.plugin in ['shell', 'resource',
                               'attachment', 'local']

    @property
    def startup_user_interaction_required(self):
        """
        The job needs to be started explicitly by the test operator. This is
        intended for things that may be timing-sensitive or may require the
        tester to understand the necessary manipulations that he or she may
        have to perform ahead of time.

        The test operator may select to skip certain tests, in that case the
        outcome is skip.
        """
        return self.plugin in ['manual', 'user-interact',
                               'user-interact-verify']

    @property
    def via(self):
        """
        The checksum of the "parent" job when the current JobDefinition comes
        from a job output using the local plugin
        """
        if hasattr(self.origin.source, 'job'):
            return self.origin.source.job.checksum

    def update_origin(self, origin):
        """
        Change the Origin object associated with this JobDefinition

        .. note::

            This method is a unfortunate side effect of how via and local jobs
            that cat existing jobs are implemented. Ideally jobs would be
            trully immutable. Do not use this method lightly.
        """
        self._origin = origin

    def get_resource_program(self):
        """
        Return a ResourceProgram based on the 'requires' expression.

        The program instance is cached in the JobDefinition and is not
        compiled or validated on subsequent calls.

        :returns:
            ResourceProgram if one is available or None
        :raises ResourceProgramError:
            If the program definition is incorrect
        """
        if self.requires is not None and self._resource_program is None:
            if self._provider is not None:
                implicit_namespace = self._provider.namespace
            else:
                implicit_namespace = None
            if self.imports is not None:
                imports = self.get_imported_jobs()
            else:
                imports = None
            self._resource_program = ResourceProgram(
                self.requires, implicit_namespace, imports)
        return self._resource_program

    def get_direct_dependencies(self):
        """
        Compute and return a set of direct dependencies

        To combat a simple mistake where the jobs are space-delimited any
        mixture of white-space (including newlines) and commas are allowed.
        """
        if self.depends:
            return {
                self.qualify_id(maybe_partial_id)
                for maybe_partial_id in re.split('[\s,]+', self.depends)
            }
        else:
            return set()

    def get_resource_dependencies(self):
        """
        Compute and return a set of resource dependencies
        """
        program = self.get_resource_program()
        if program:
            return program.required_resources
        else:
            return set()

    def get_category_id(self):
        """
        Get the fully-qualified category id that this job belongs to
        """
        maybe_partial_id = self.category_id
        if maybe_partial_id is not None:
            return self.qualify_id(maybe_partial_id)

    @classmethod
    def from_rfc822_record(cls, record, provider=None):
        """
        Create a JobDefinition instance from rfc822 record. The resulting
        instance may not be valid but will always be created. Only valid jobs
        should be executed.

        The record must be a RFC822Record instance.
        """
        # Strip the trailing newlines form all the raw values coming from the
        # RFC822 parser. We don't need them and they don't match gettext keys
        # (xgettext strips out those newlines)
        return cls(record.data, record.origin, provider=provider, raw_data={
            key: value.rstrip('\n')
            for key, value in record.raw_data.items()
        }, field_offset_map=record.field_offset_map)

    def create_child_job_from_record(self, record):
        """
        Create a new JobDefinition from RFC822 record.

        This method should only be used to create additional jobs from local
        jobs (plugin local). This ensures that the child job shares the
        embedded provider reference.
        """
        if not isinstance(record.origin.source, JobOutputTextSource):
            # TRANSLATORS: don't translate record.origin or JobOutputTextSource
            raise ValueError(_("record.origin must be a JobOutputTextSource"))
        if record.origin.source.job is not self:
            # TRANSLATORS: don't translate record.origin.source.job
            raise ValueError(_("record.origin.source.job must be this job"))
        return self.from_rfc822_record(record, self.provider)

    class Meta(UnitWithId.Meta, JobDefinitionLegacyAPI.Meta):

        class fields(UnitWithId.Meta.fields):
            """
            Symbols for each field that a JobDefinition can have
            """
            name = 'name'
            summary = 'summary'
            plugin = 'plugin'
            command = 'command'
            description = 'description'
            user = 'user'
            environ = 'environ'
            estimated_duration = 'estimated_duration'
            depends = 'depends'
            requires = 'requires'
            shell = 'shell'
            imports = 'imports'
            flags = 'flags'
            category_id = 'category_id'

        field_validators = {}
        field_validators.update(UnitWithId.Meta.field_validators)
        field_validators.update({
            fields.name: [
                UntranslatableFieldValidator,
                TemplateVariantFieldValidator,
                DeprecatedFieldValidator(
                    _("use 'id' and 'summary' instead of 'name'")),
            ],
            # NOTE: 'id' validators are "inherited" so we don't have it here
            fields.summary: [
                TranslatableFieldValidator,
                TemplateVariantFieldValidator,
                PresentFieldValidator(severity=Severity.advice),
                # We want the summary to be a single line
                CorrectFieldValueValidator(
                    lambda summary: summary.count("\n") == 0,
                    Problem.wrong, Severity.warning,
                    message=_("please use only one line"),
                    onlyif=lambda unit: unit.summary is not None),
                # We want the summary to be relatively short
                CorrectFieldValueValidator(
                    lambda summary: len(summary) <= 80,
                    Problem.wrong, Severity.warning,
                    message=_("please stay under 80 characters"),
                    onlyif=lambda unit: unit.summary is not None),
            ],
            fields.plugin: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                PresentFieldValidator,
                CorrectFieldValueValidator(
                    lambda plugin: (
                        plugin in JobDefinition.plugin.get_all_symbols()),
                    message=_('valid values are: {}').format(
                        ', '.join(str(sym) for sym in sorted(
                            _PluginValues.get_all_symbols())))),
                CorrectFieldValueValidator(
                    lambda plugin: plugin != 'local',
                    Problem.deprecated, Severity.advice,
                    message=_("please migrate to job templates, "
                              "see plainbox-template-unit(7) for details")),
                CorrectFieldValueValidator(
                    lambda plugin: plugin != 'user-verify',
                    Problem.deprecated, Severity.advice,
                    message=_("please migrate to user-interact-verify")),
            ],
            fields.command: [
                UntranslatableFieldValidator,
                TemplateVariantFieldValidator,
                # All jobs except for manual must have a command
                PresentFieldValidator(
                    message=_("command is mandatory for non-manual jobs"),
                    onlyif=lambda unit: unit.plugin != 'manual'),
                # Manual jobs cannot have a command
                UselessFieldValidator(
                    message=_("command on a manual job makes no sense"),
                    onlyif=lambda unit: unit.plugin == 'manual'),
                # We don't want to refer to CHECKBOX_SHARE anymore
                CorrectFieldValueValidator(
                    lambda command: "CHECKBOX_SHARE" not in command,
                    Problem.deprecated, Severity.advice,
                    message=_("please use PLAINBOX_PROVIDER_DATA"
                              " instead of CHECKBOX_SHARE"),
                    onlyif=lambda unit: unit.command is not None),
                # We don't want to refer to CHECKBOX_DATA anymore
                CorrectFieldValueValidator(
                    lambda command: "CHECKBOX_DATA" not in command,
                    Problem.deprecated, Severity.advice,
                    message=_("please use PLAINBOX_SESSION_SHARE"
                              " instead of CHECKBOX_DATA"),
                    onlyif=lambda unit: unit.command is not None),
                # We want to catch silly mistakes that shlex can detect
                ShellProgramValidator,
            ],
            fields.description: [
                TranslatableFieldValidator,
                TemplateVariantFieldValidator,
                # Description is mandatory for manual jobs
                PresentFieldValidator(
                    message=_("manual jobs must have a description"),
                    onlyif=lambda unit: unit.plugin == 'manual'),
                # Description is recommended for all other jobs
                PresentFieldValidator(
                    severity=Severity.advice,
                    message=_("all jobs should have a description"),
                    onlyif=lambda unit: unit.plugin != 'manual')
            ],
            fields.user: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                # User should be either None or 'root'
                CorrectFieldValueValidator(
                    message=_("user can only be 'root'"),
                    correct_fn=lambda user: user in (None, 'root')),
                # User is useless without a command to run
                UselessFieldValidator(
                    message=_("user without a command makes no sense"),
                    onlyif=lambda unit: unit.command is None)
            ],
            fields.environ: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                # Environ is useless without a command to run
                UselessFieldValidator(
                    message=_("environ without a command makes no sense"),
                    onlyif=lambda unit: unit.command is None),
            ],
            fields.estimated_duration: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                PresentFieldValidator(severity=Severity.advice),
                CorrectFieldValueValidator(
                    lambda duration: float(duration) > 0,
                    message="value must be a positive number",
                    onlyif=lambda unit: (
                        unit.get_record_value('estimated_duration'))),
            ],
            fields.depends: [
                UntranslatableFieldValidator,
                CorrectFieldValueValidator(
                    lambda value, unit: (
                        unit.get_direct_dependencies() is not None)),
                UnitReferenceValidator(
                    lambda unit: unit.get_direct_dependencies(),
                    constraints=[
                        ReferenceConstraint(
                            lambda referrer, referee: referee.unit == 'job',
                            message=_("the referenced unit is not a job"))])
                # TODO: should not refer to deprecated jobs,
                #       onlyif job itself is not deprecated
            ],
            fields.requires: [
                UntranslatableFieldValidator,
                CorrectFieldValueValidator(
                    lambda value, unit: unit.get_resource_program(),
                    onlyif=lambda unit: unit.requires is not None),
                UnitReferenceValidator(
                    lambda unit: unit.get_resource_dependencies(),
                    constraints=[
                        ReferenceConstraint(
                            lambda referrer, referee: referee.unit == 'job',
                            message=_("the referenced unit is not a job")),
                        ReferenceConstraint(
                            lambda referrer, referee: (
                                referee.plugin == 'resource'),
                            onlyif=lambda referrer, referee: (
                                referee.unit == 'job'),
                            message=_(
                                "the referenced job is not a resource job")),
                    ]),
                # TODO: should not refer to deprecated jobs,
                #       onlyif job itself is not deprecated
            ],
            fields.shell: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                # Shell should be only '/bin/sh', or None (which gives bash)
                CorrectFieldValueValidator(
                    lambda shell: shell in ('/bin/sh', '/bin/bash', 'bash'),
                    message=_("only /bin/sh and /bin/bash are allowed")),
            ],
            fields.imports: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                CorrectFieldValueValidator(
                    lambda value, unit: (
                        list(unit.get_imported_jobs()) is not None)),
                UnitReferenceValidator(
                    lambda unit: [
                        job_id
                        for job_id, identifier in unit.get_imported_jobs()],
                    constraints=[
                        ReferenceConstraint(
                            lambda referrer, referee: referee.unit == 'job',
                            message=_("the referenced unit is not a job"))]),
                # TODO: should not refer to deprecated jobs,
                #       onlyif job itself is not deprecated
            ],
            fields.category_id: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                UnitReferenceValidator(
                    lambda unit: (
                        [unit.get_category_id()] if unit.category_id else ()),
                    constraints=[
                        ReferenceConstraint(
                            lambda referrer, referee: (
                                referee.unit == 'category'),
                            message=_(
                                "the referenced unit is not a category"))]),
                # TODO: should not refer to deprecated categories,
                #       onlyif job itself is not deprecated
            ],
            fields.flags: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                CorrectFieldValueValidator(
                    lambda value, unit: (
                        'preserve-locale' in unit.get_flag_set()),
                    Problem.expected_i18n, Severity.advice,
                    message=_(
                        'please ensure that the command supports'
                        ' non-C locale then set the preserve-locale flag'
                    ),
                    onlyif=lambda unit: unit.command),
            ]
        })


JobDefinition.fields = JobDefinition.Meta.fields
