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
:mod:`plainbox.impl.unit.job` -- job unit
=========================================
"""

import logging
import operator
import re
import sre_constants
import sre_parse

from plainbox.i18n import gettext as _
from plainbox.impl.secure.qualifiers import CompositeQualifier
from plainbox.impl.secure.qualifiers import FieldQualifier
from plainbox.impl.secure.qualifiers import OperatorMatcher
from plainbox.impl.secure.qualifiers import PatternMatcher
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit._legacy import TestPlanUnitLegacyAPI
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import compute_value_map
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import FieldValidatorBase
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import TemplateInvariantFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity


logger = logging.getLogger("plainbox.unit.testplan")


__all__ = ['TestPlanUnit']


class NonEmptyPatternIntersectionValidator(FieldValidatorBase):
    """
    We want to ensure that it is a good pattern, we need to parse it
    to see the fine structure and know what it describes.
    We want to ensure it describes a known job, either precisely
    """

    def check_in_context(self, parent, unit, field, context):
        for issue in self._check_test_plan_in_context(
                parent, unit, field, context):
            yield issue

    def _check_test_plan_in_context(self, parent, unit, field, context):
        id_map = context.compute_shared(
            "field_value_map[id]", compute_value_map, context, 'id')
        # TODO: compute potential_id_map
        advice = _("selector {!a} may not match any known or generated job")
        error = _("selector {!a} doesn't match any known or generated job")
        qual_gen = unit._gen_qualifiers(
            str(field), getattr(unit, str(field)), True)
        for qual in qual_gen:
            assert isinstance(qual, FieldQualifier)
            if qual.field != 'id':
                # NOTE: unsupported field
                continue
            if isinstance(qual.matcher, PatternMatcher):
                # TODO: check potential_id map
                for an_id in id_map:
                    if qual.matcher.match(an_id):
                        break
                else:
                    yield parent.advice(
                        unit, field, Problem.bad_reference,
                        advice.format(qual.matcher.pattern_text),
                        origin=qual.origin)
            elif isinstance(qual.matcher, OperatorMatcher):
                assert qual.matcher.op is operator.eq
                target_id = qual.matcher.value
                if target_id not in id_map:
                    assert qual.origin.source is unit.origin.source
                    yield parent.error(
                        unit, field, Problem.bad_reference,
                        error.format(target_id),
                        origin=qual.origin)
            else:
                # NOTE: unsupported matcher
                raise NotImplementedError


class TestPlanUnit(UnitWithId, TestPlanUnitLegacyAPI):
    """
    Test plan class

    A container for a named selection of jobs to run and additional meta-data
    useful for various user interfaces.
    """

    def __str__(self):
        """
        same as .name
        """
        return self.name

    def __repr__(self):
        return "<TestPlanUnit id:{!r} name:{!r}>".format(self.id, self.name)

    @property
    def name(self):
        """
        name of this test plan

        .. note::
            This value is not translated, see :meth:`tr_name()` for
            a translated equivalent.
        """
        return self.get_record_value('name')

    @property
    def description(self):
        """
        description of this test plan

        .. note::
            This value is not translated, see :meth:`tr_name()` for
            a translated equivalent.
        """
        return self.get_record_value('description')

    @property
    def include(self):
        return self.get_record_value('include')

    @property
    def exclude(self):
        return self.get_record_value('exclude')

    @property
    def icon(self):
        return self.get_record_value('icon')

    @property
    def category_overrides(self):
        return self.get_record_value('category-overrides')

    @property
    def estimated_duration(self):
        """
        estimated duration of this test plan in seconds.

        The value may be None, which indicates that the duration is basically
        unknown. Fractional numbers are allowed and indicate fractions of a
        second.
        """
        value = self.get_record_value('estimated_duration')
        if value is None:
            return
        return float(value)

    def tr_name(self):
        """
        Get the translated version of :meth:`summary`
        """
        return self.get_translated_record_value('name')

    def tr_description(self):
        """
        Get the translated version of :meth:`description`
        """
        return self.get_translated_record_value('description')

    def get_qualifier(self):
        """
        Convert this test plan to an equivalent qualifier for job selection

        :returns:
            A CompositeQualifier corresponding to the contents of both
            the include and exclude fields.
        """
        qual_list = []
        qual_list.extend(self._gen_qualifiers('include', self.include, True))
        qual_list.extend(self._gen_qualifiers('exclude', self.exclude, False))
        return CompositeQualifier(qual_list)

    def _gen_qualifiers(self, field_name, field_value, inclusive):
        if field_value is not None:
            field_origin = self.origin.just_line().with_offset(
                self.field_offset_map[field_name])
            matchers_gen = self.parse_matchers(field_value)
            for lineno_offset, matcher_field, matcher, error in matchers_gen:
                if error is not None:
                    raise error
                offset = field_origin.with_offset(lineno_offset)
                yield FieldQualifier(matcher_field, matcher, offset, inclusive)

    def parse_matchers(self, text):
        """
        Parse the specified text and create a list of matchers

        :param text:
            string of text, including newlines and comments, to parse
        :returns:
            A generator returning quads (lineno_offset, field, matcher, error)
            where ``lineno_offset`` is the offset of a line number from the
            start of the text, ``field`` is the name of the field in a job
            definition unit that the matcher should be applied,
            ``matcher`` can be None (then ``error`` is relevant) or one of
            the ``IMatcher`` subclasses discussed below.

        Supported matcher objects include:

        PatternMatcher:
            This matcher is created for lines of text that **are** regular
            expressions. The pattern is automatically expanded to include
            ^...$ (if missing) so that it cannot silently match a portion of
            a job definition

        OperatorMatcher:
            This matcher is created for lines of text that **are not** regular
            expressions. The matcher uses the operator.eq operator (equality)
            and stores the expected job identifier as the right-hand-side value
        """
        for lineno_offset, line in enumerate(text.splitlines()):
            # Strip shell-style comments if there are any
            try:
                index = line.index("#")
            except ValueError:
                pass
            else:
                line = line[:index]
            # Strip whitespace
            line = line.strip()
            # Skip empty lines (especially after stripping comments)
            if line == "":
                continue
            # TODO: add a way to define custom fields
            # with a syntax like: FIELD: PATTERN
            # eg: category_id: 2013\.com\.canonical\.plainbox::audio
            field = 'id'
            value = line
            try:
                re_ast = sre_parse.parse(value)
            except sre_constants.error as exc:
                error = exc
                matcher = None
            else:
                error = None
                # check if the AST of this regular expression is composed
                # of just a flat list of 'literal' nodes. In other words,
                # check if it is a simple string match in disguise
                if all(t == 'literal' for t, rest in re_ast):
                    target_id = self.qualify_id(value)
                    matcher = OperatorMatcher(operator.eq, target_id)
                else:
                    # Ensure that pattern is surrounded by ^ and $
                    if value.startswith('^') and value.endswith('$'):
                        target_id_pattern = '^{}$'.format(
                            self.qualify_id(value[1:-1]))
                    elif value.startswith('^'):
                        target_id_pattern = '^{}$'.format(
                            self.qualify_id(value[1:]))
                    elif value.endswith('$'):
                        target_id_pattern = '^{}$'.format(
                            self.qualify_id(value[:-1]))
                    else:
                        target_id_pattern = '^{}$'.format(
                            self.qualify_id(value))
                    # NOTE: this cannot fail as we have parsed the expression
                    # already and our transformations above should *not* harm
                    # it in any way.
                    matcher = PatternMatcher(target_id_pattern)
            yield (lineno_offset, field, matcher, error)

    def parse_category_overrides(self, text):
        """
        Parse the specified text as a list of category overrides.

        :param text:
            string of text, including newlines and comments, to parse
        :returns:
            A list of tuples (lineno_offset, category_id, pattern) where
            lineno_offset is the line number offset from the start of the text,
            category_id is the desired category identifier and pattern is the
            actual regular expression text (which may be invalid).
        :raises ValueError:
            if there are any issues with the override declarations
        """
        from plainbox.impl.xparsers import Error
        from plainbox.impl.xparsers import FieldOverride
        from plainbox.impl.xparsers import OverrideFieldList
        from plainbox.impl.xparsers import Visitor

        outer_self = self

        class OverrideListVisitor(Visitor):

            def __init__(self):
                self.override_list = []

            def visit_FieldOverride_node(self, node: FieldOverride):
                category_id = outer_self.qualify_id(node.value.text)
                regexp_pattern = r"^{}$".format(
                    outer_self.qualify_id(node.pattern.text))
                self.override_list.append(
                    (node.lineno, category_id, regexp_pattern))

            def visit_Error_node(self, node: Error):
                raise ValueError(node.msg)

        visitor = OverrideListVisitor()
        visitor.visit(OverrideFieldList.parse(text, 0, 0))
        return visitor.override_list

    def get_effective_category_map(self, job_list):
        """
        Compute the effective category association for the given list of jobs

        :param job_list:
            a list of JobDefinition units
        :returns:
            A dictionary mapping job.id to the effective category_id. Note that
            category_id may be None or may not refer to a valid, known
            category. The caller is responsible for validating that.
        """
        effective_map = {job.id: job.category_id for job in job_list}
        if self.category_overrides is not None:
            overrides_gen = self.parse_category_overrides(
                self.category_overrides)
            for lineno_offset, category_id, pattern in overrides_gen:
                for job in job_list:
                    if re.match(pattern, job.id):
                        effective_map[job.id] = category_id
        return effective_map

    def get_effective_category(self, job):
        """
        Compute the effective category association for a single job

        :param job:
            a JobDefinition units
        :returns:
            The effective category_id
        """
        if self.category_overrides is not None:
            overrides_gen = self.parse_category_overrides(
                self.category_overrides)
            for lineno_offset, category_id, pattern in overrides_gen:
                if re.match(pattern, job.id):
                    return category_id
        return job.category_id

    class Meta:

        name = 'test plan'

        class fields(SymbolDef):
            """
            Symbols for each field that a TestPlan can have
            """
            name = 'name'
            description = 'description'
            include = 'include'
            exclude = 'exclude'
            estimated_duration = 'estimated_duration'
            icon = 'icon'
            category_overrides = 'category-overrides'

        field_validators = {
            fields.name: [
                TranslatableFieldValidator,
                TemplateVariantFieldValidator,
                PresentFieldValidator,
                # We want the summary to be a single line
                CorrectFieldValueValidator(
                    lambda name: name.count("\n") == 0,
                    Problem.wrong, Severity.warning,
                    message=_("please use only one line"),
                    onlyif=lambda unit: unit.name is not None),
                # We want the summary to be relatively short
                CorrectFieldValueValidator(
                    lambda name: len(name) <= 80,
                    Problem.wrong, Severity.warning,
                    message=_("please stay under 80 characters"),
                    onlyif=lambda unit: unit.name is not None),
            ],
            fields.description: [
                TranslatableFieldValidator,
                TemplateVariantFieldValidator,
                PresentFieldValidator(
                    severity=Severity.advice,
                    onlyif=lambda unit: unit.virtual is False),
            ],
            fields.include: [
                NonEmptyPatternIntersectionValidator,
            ],
            fields.exclude: [
                NonEmptyPatternIntersectionValidator,
            ],
            fields.estimated_duration: [
                UntranslatableFieldValidator,
                TemplateInvariantFieldValidator,
                PresentFieldValidator(
                    severity=Severity.advice,
                    onlyif=lambda unit: unit.virtual is False),
                CorrectFieldValueValidator(
                    lambda duration, unit: float(
                        unit.get_record_value('estimated_duration')) > 0,
                    message="value must be a positive number",
                    onlyif=lambda unit: (
                        unit.virtual is False
                        and unit.get_record_value('estimated_duration'))),
            ],
            fields.icon: [
                UntranslatableFieldValidator,
            ],
            fields.category_overrides: [
                # optional
                # valid
                # referring to jobs correctly
                # referring to categories correctly
            ],
        }
