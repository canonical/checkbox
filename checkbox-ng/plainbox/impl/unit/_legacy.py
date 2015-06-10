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
:mod:`plainbox.impl.unit` -- unit definition
============================================

Module with implementation of legacy validation API for all the current units.
This module can be removed once that API is no longer needed.
"""
import itertools

from plainbox.i18n import gettext as _
from plainbox.impl import deprecated
from plainbox.impl.resource import Resource
from plainbox.impl.resource import ResourceProgramError
from plainbox.impl.validation import Problem
from plainbox.impl.validation import ValidationError

# --- validators ---


class UnitValidatorLegacyAPI:

    @deprecated('0.11', 'use get_issues() instead')
    def validate(self, unit, strict=False, deprecated=False):
        """
        Validate data stored in the unit

        :param validation_kwargs:
            Validation parameters (may vary per subclass)
        :raises ValidationError:
            If the unit is incorrect somehow.

        Non-parametric units are always valid. Parametric units are valid if
        they don't violate the parametric constraints encoded in the
        :class:`Unit.Meta` unit meta-data class'
        :attr:`Unit.Meta.template_constraints` field.
        """
        # Non-parametric units are always valid
        if not unit.is_parametric:
            return
        # Parametric units should obey the parametric constraints (encoded in
        # the helper meta-data class Meta's template_constraints field)
        for field, param_set in unit.get_accessed_parameters().items():
            constraint = unit.Meta.template_constraints.get(field)
            # Fields cannot refer to parameters that we don't have
            for param_name in param_set:
                if param_name not in unit.parameters:
                    raise ValidationError(field, Problem.wrong)
            # Fields without constraints are otherwise valid.
            if constraint is None:
                continue
            assert constraint in ('vary', 'const')
            # Fields that need to be variable cannot have a non-parametrized
            # value
            if constraint == 'vary' and len(param_set) == 0:
                raise ValidationError(field, Problem.constant)
            # Fields that need to be constant cannot have parametrized value
            elif constraint == 'const' and len(param_set) != 0:
                raise ValidationError(field, Problem.variable)


class UnitWithIdValidatorLegacyAPI(UnitValidatorLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, unit, strict=False, deprecated=False):
        super().validate(unit, strict, deprecated)
        # Check if the partial_id field is empty
        if unit.partial_id is None:
            raise ValidationError("id", Problem.missing)


class JobDefinitionValidatorLegacyAPI(UnitWithIdValidatorLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, job, strict=False, deprecated=False):
        """
        Validate the specified job

        :param strict:
            Enforce strict validation. Non-conforming jobs will be rejected.
            This is off by default to ensure that non-critical errors don't
            prevent jobs from running.
        :param deprecated:
            Enforce deprecation validation. Jobs having deprecated fields will
            be rejected. This is off by default to allow backwards compatible
            jobs to be used without any changes.
        """
        super().validate(job, strict, deprecated)
        from plainbox.impl.unit.job import JobDefinition
        # Check if name is still being used, if running in strict mode
        if deprecated and job.get_record_value('name') is not None:
            raise ValidationError(job.fields.name, Problem.deprecated)
        # Check if the partial_id field is empty
        if job.partial_id is None:
            raise ValidationError(job.fields.id, Problem.missing)
        # Check if summary is empty, if running in strict mode
        if strict and job.summary is None:
            raise ValidationError(job.fields.summary, Problem.missing)
        # Check if plugin is empty
        if job.plugin is None:
            raise ValidationError(job.fields.plugin, Problem.missing)
        # Check if plugin has a good value
        elif job.plugin not in JobDefinition.plugin.get_all_symbols():
            raise ValidationError(job.fields.plugin, Problem.wrong)
        # Check if user is given without a command to run, if running in strict
        # mode
        if strict and job.user is not None and job.command is None:
            raise ValidationError(job.fields.user, Problem.useless)
        # Check if environ is given without a command to run, if running in
        # strict mode
        if strict and job.environ is not None and job.command is None:
            raise ValidationError(job.fields.environ, Problem.useless)
        # Verify that command is present on a job within the subset that should
        # really have them (shell, local, resource, attachment, user-verify and
        # user-interact)
        if job.plugin in {JobDefinition.plugin.shell,
                          JobDefinition.plugin.local,
                          JobDefinition.plugin.resource,
                          JobDefinition.plugin.attachment,
                          JobDefinition.plugin.user_verify,
                          JobDefinition.plugin.user_interact,
                          JobDefinition.plugin.user_interact_verify}:
            # Check if shell jobs have a command
            if job.command is None:
                raise ValidationError(job.fields.command, Problem.missing)
            # Check if user has a good value
            if job.user not in (None, "root"):
                raise ValidationError(job.fields.user, Problem.wrong)
        # Do some special checks for manual jobs as those should really be
        # fully interactive, non-automated jobs (otherwise they are either
        # user-interact or user-verify)
        if job.plugin == JobDefinition.plugin.manual:
            # Ensure that manual jobs have a description
            if job.description is None:
                raise ValidationError(
                    job.fields.description, Problem.missing)
            # Ensure that manual jobs don't have command, if running in strict
            # mode
            if strict and job.command is not None:
                raise ValidationError(job.fields.command, Problem.useless)
        estimated_duration = job.get_record_value('estimated_duration')
        if estimated_duration is not None:
            try:
                float(estimated_duration)
            except ValueError:
                raise ValidationError(
                    job.fields.estimated_duration, Problem.wrong)
        elif strict and estimated_duration is None:
            raise ValidationError(
                job.fields.estimated_duration, Problem.missing)
        # The resource program should be valid
        try:
            job.get_resource_program()
        except ResourceProgramError:
            raise ValidationError(job.fields.requires, Problem.wrong)


class TemplateUnitValidatorLegacyAPI(UnitValidatorLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, template, strict=False, deprecated=False):
        """
        Validate the specified job template

        :param strict:
            Enforce strict validation. Non-conforming jobs will be rejected.
            This is off by default to ensure that non-critical errors don't
            prevent jobs from running.
        :param deprecated:
            Enforce deprecation validation. Jobs having deprecated fields will
            be rejected. This is off by default to allow backwards compatible
            jobs to be used without any changes.
        """
        super().validate(template, strict, deprecated)
        # All templates need the template-resource field
        if template.template_resource is None:
            raise ValidationError(
                template.fields.template_resource, Problem.missing)
        # All templates need a valid (or empty) template filter
        try:
            template.get_filter_program()
        except (ResourceProgramError, SyntaxError) as exc:
            raise ValidationError(
                template.fields.template_filter, Problem.wrong,
                hint=str(exc))
        # All templates should use the resource object correctly. This is
        # verified by the code below. It generally means that fields should or
        # should not use variability induced by the resource object data.
        accessed_parameters = template.get_accessed_parameters(force=True)
        # The unit field must be constant.
        if ('unit' in accessed_parameters
                and len(accessed_parameters['unit']) != 0):
            raise ValidationError(template.fields.id, Problem.variable)
        # Now that we know it's constant we can look up the unit it is supposed
        # to instantiate.
        try:
            unit_cls = template.get_target_unit_cls()
        except LookupError:
            raise ValidationError(template.fields.unit, Problem.wrong)
        # Let's look at the template constraints for the unit
        for field, constraint in unit_cls.Meta.template_constraints.items():
            assert constraint in ('vary', 'const')
            if constraint == 'vary':
                if (field in accessed_parameters
                        and len(accessed_parameters[field]) == 0):
                    raise ValidationError(field, Problem.constant)
            elif constraint == 'const':
                if (field in accessed_parameters
                        and len(accessed_parameters[field]) != 0):
                    raise ValidationError(field, Problem.variable)
        # Lastly an example unit generated with a fake resource should still be
        resource = self._get_fake_resource(accessed_parameters)
        unit = template.instantiate_one(resource, unit_cls_hint=unit_cls)
        return unit.validate(strict=strict, deprecated=deprecated)

    @classmethod
    def _get_fake_resource(cls, accessed_parameters):
        return Resource({
            key: key.upper()
            for key in set(itertools.chain(*accessed_parameters.values()))
        })


class CategoryUnitValidatorLegacyAPI(UnitWithIdValidatorLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, unit, strict=False, deprecated=False):
        """
        Validate the specified category

        :param unit:
            :class:`CategoryUnit` to validate
        :param strict:
            Enforce strict validation. Non-conforming categories will be
            rejected. This is off by default to ensure that non-critical errors
            don't prevent categories from being used.
        :param deprecated:
            Enforce deprecation validation. Categories having deprecated fields
            will be rejected. This is off by default to allow backwards
            compatible categories to be used without any changes.
        """
        # Check basic stuff
        super().validate(unit, strict=strict, deprecated=deprecated)
        # Check if name is empty
        if unit.name is None:
            raise ValidationError(unit.fields.name, Problem.missing)


class TestPlanUnitValidatorLegacyAPI(UnitWithIdValidatorLegacyAPI):
    """
    Validator for :class:`TestPlanUnit`
    """

    @deprecated('0.11', 'use .check() instead')
    def validate(self, unit, **validation_kwargs):
        # Check basic stuff
        super().validate(unit, **validation_kwargs)
        # Check if name field is empty
        if unit.name is None:
            raise ValidationError("name", Problem.missing)
        # Check that we can convert include + exclude into a list of qualifiers
        # this is not perfect but it has some sort of added value
        if unit.include is not None:
            self._validate_selector(unit, "include")
        if unit.exclude is not None:
            self._validate_selector(unit, "exclude")
        # check if .estimated_duration crashes on ValueError
        try:
            unit.estimated_duration
        except ValueError:
            raise ValidationError("estimated_duration", Problem.wrong)

    def _validate_selector(self, unit, field_name):
        field_value = getattr(unit, field_name)
        matchers_gen = unit.parse_matchers(field_value)
        for lineno_offset, matcher_field, matcher, error in matchers_gen:
            if error is None:
                continue
            raise ValidationError(
                field_name, Problem.wrong,
                hint=_("invalid regular expression: {0}".format(str(error))),
                origin=unit.origin.with_offset(
                    lineno_offset + unit.field_offset_map[field_name]
                ).just_line())


# --- units ---


class UnitLegacyAPI:

    @deprecated("0.7", "call unit.tr_unit() instead")
    def get_unit_type(self):
        return self.tr_unit()

    @deprecated('0.11', 'use .check() instead')
    def validate(self, **validation_kwargs):
        """
        Validate data stored in the unit

        :param validation_kwargs:
            Validation parameters (may vary per subclass)
        :raises ValidationError:
            If the unit is incorrect somehow.

        Non-parametric units are always valid. Parametric units are valid if
        they don't violate the parametric constraints encoded in the
        :class:`Unit.Meta` unit meta-data class'
        :attr:`Unit.Meta.template_constraints` field.
        """
        return UnitValidatorLegacyAPI().validate(self, **validation_kwargs)

    class Meta:

        template_constraints = {
            'unit': 'const'
        }


class UnitWithIdLegacyAPI(UnitLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, **validation_kwargs):
        """
        Validate data stored in the unit

        :param validation_kwargs:
            Validation parameters (may vary per subclass)
        :raises ValidationError:
            If the unit is incorrect somehow.

        Non-parametric units are always valid. Parametric units are valid if
        they don't violate the parametric constraints encoded in the
        :class:`Unit.Meta` unit meta-data class'
        :attr:`Unit.Meta.template_constraints` field.
        """
        return UnitWithIdValidatorLegacyAPI().validate(
            self, **validation_kwargs)

    class Meta(UnitLegacyAPI.Meta):

        template_constraints = dict(UnitLegacyAPI.Meta.template_constraints)
        template_constraints.update({
            'id': 'vary'
        })


class JobDefinitionLegacyAPI(UnitWithIdLegacyAPI):

    @property
    @deprecated('0.11', 'use .partial_id or .summary instead')
    def name(self):
        return self.get_record_value('name')

    def validate(self, **validation_kwargs):
        """
        Validate this job definition

        :param validation_kwargs:
            Keyword arguments to pass to the
            :meth:`JobDefinitionValidator.validate()`
        :raises ValidationError:
            If the job has any problems that make it unsuitable for execution.
        """
        JobDefinitionValidatorLegacyAPI().validate(
            self, **validation_kwargs)

    class Meta(UnitWithIdLegacyAPI.Meta):

        template_constraints = {
            'name': 'vary',
            'unit': 'const',
            # The 'id' field should be always variable (depending on at least
            # resource reference) or clashes are inevitable (they can *still*
            # occur but this is something we cannot prevent).
            'id': 'vary',
            # The summary should never be constant as that would be confusing
            # to the test operator. If it is defined in the template it should
            # be customized by at least one resource reference.
            'summary': 'vary',
            # The 'plugin' field should be constant as otherwise validation is
            # very unreliable. There is no current demand for being able to
            # customize it from a resource record.
            'plugin': 'const',
            # The description should never be constant as that would be
            # confusing to the test operator. If it is defined in the template
            # it should be customized by at least one resource reference.
            'description': 'vary',
            # There is no conceivable value in having a variable user field
            'user': 'const',
            'environ': 'const',
            # TODO: what about estimated duration?
            # 'estimated_duration': '?',
            # TODO: what about depends and requires?
            #
            # If both are const then we can determine test ordering without any
            # action and the ordering is not perturbed at runtime. This may be
            # too strong of a limitation though. We'll see.
            # 'depends': '?',
            # 'requires': '?',
            'shell': 'const',
            'imports': 'const',
            'category_id': 'const',
        }


class CategoryUnitLegacyAPI(UnitWithIdLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, **validation_kwargs):
        """
        Validate this job definition

        :param validation_kwargs:
            Keyword arguments to pass to the
            :meth:`CategoryUnitValidator.validate()`
        :raises ValidationError:
            If the category has any problems.
        """
        return CategoryUnitValidatorLegacyAPI().validate(
            self, **validation_kwargs)

    class Meta(UnitWithIdLegacyAPI.Meta):

        template_constraints = dict(
            UnitWithIdLegacyAPI.Meta.template_constraints)
        template_constraints.update({
            # The name field should vary so that instantiated categories
            # have different user-visible names
            'name': 'vary',
        })


class TemplateUnitLegacyAPI(UnitLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, **validation_kwargs):
        """
        Validate this job definition template

        :param validation_kwargs:
            Keyword arguments to pass to the
            :meth:`TemplateUnitValidator.validate()`
        :raises ValidationError:
            If the template has any problems that make it unsuitable for
            execution.
        """
        return TemplateUnitValidatorLegacyAPI().validate(
            self, **validation_kwargs)

    class Meta(UnitLegacyAPI.Meta):
        pass


class TestPlanUnitLegacyAPI(UnitWithIdLegacyAPI):

    @deprecated('0.11', 'use .check() instead')
    def validate(self, **validation_kwargs):
        """
        Validate data stored in the unit

        :param validation_kwargs:
            Validation parameters (may vary per subclass)
        :raises ValidationError:
            If the unit is incorrect somehow.

        Non-parametric units are always valid. Parametric units are valid if
        they don't violate the parametric constraints encoded in the
        :class:`Unit.Meta` unit meta-data class'
        :attr:`Unit.Meta.template_constraints` field.
        """
        return TestPlanUnitValidatorLegacyAPI().validate(
            self, **validation_kwargs)
