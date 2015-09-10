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
import collections
import logging
import operator
import re

from plainbox.i18n import gettext as _
from plainbox.impl.secure.qualifiers import CompositeQualifier
from plainbox.impl.secure.qualifiers import FieldQualifier
from plainbox.impl.secure.qualifiers import OperatorMatcher
from plainbox.impl.secure.qualifiers import PatternMatcher
from plainbox.impl.symbol import SymbolDef
from plainbox.impl.unit._legacy import TestPlanUnitLegacyAPI
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import CorrectFieldValueValidator
from plainbox.impl.unit.validators import FieldValidatorBase
from plainbox.impl.unit.validators import PresentFieldValidator
from plainbox.impl.unit.validators import ReferenceConstraint
from plainbox.impl.unit.validators import TemplateInvariantFieldValidator
from plainbox.impl.unit.validators import TemplateVariantFieldValidator
from plainbox.impl.unit.validators import TranslatableFieldValidator
from plainbox.impl.unit.validators import UnitReferenceValidator
from plainbox.impl.unit.validators import UntranslatableFieldValidator
from plainbox.impl.unit.validators import compute_value_map
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity
from plainbox.impl.xparsers import Error
from plainbox.impl.xparsers import FieldOverride
from plainbox.impl.xparsers import IncludeStmt
from plainbox.impl.xparsers import IncludeStmtList
from plainbox.impl.xparsers import OverrideFieldList
from plainbox.impl.xparsers import ReFixed
from plainbox.impl.xparsers import RePattern
from plainbox.impl.xparsers import Text
from plainbox.impl.xparsers import Visitor
from plainbox.impl.xparsers import WordList


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
        # error = _("selector {!a} doesn't match any known or generated job")
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
                    if an_id is None:
                        # Don't report this twice.
                        # Each unit-with-id cares about having an id
                        continue
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
                    yield parent.advice(
                        unit, field, Problem.bad_reference,
                        advice.format(target_id),
                        origin=qual.origin)
            else:
                # NOTE: unsupported matcher
                raise NotImplementedError


class NoBaseIncludeValidator(FieldValidatorBase):
    """
    We want to ensure it does not select jobs already selected by the 'include'
    field patterns.
    """

    def check_in_context(self, parent, unit, field, context):
        for issue in self._check_test_plan_in_context(
                parent, unit, field, context):
            yield issue

    def _check_test_plan_in_context(self, parent, unit, field, context):
        included_job_id = []
        id_map = context.compute_shared(
            "field_value_map[id]", compute_value_map, context, 'id')
        warning = _("selector {!a} will select a job already matched by the "
                    "'include' field patterns")
        qual_gen = unit._gen_qualifiers(
            'include', getattr(unit, 'include'), True)
        # Build the list of all jobs already included with the normal include
        # field
        for qual in qual_gen:
            assert isinstance(qual, FieldQualifier)
            if qual.field != 'id':
                continue
            if isinstance(qual.matcher, PatternMatcher):
                for an_id in id_map:
                    if an_id is None:
                        continue
                    if qual.matcher.match(an_id):
                        included_job_id.append(an_id)
            elif isinstance(qual.matcher, OperatorMatcher):
                assert qual.matcher.op is operator.eq
                target_id = qual.matcher.value
                if target_id in id_map:
                    included_job_id.append(target_id)
            else:
                raise NotImplementedError
        # Now check that mandatory field patterns do not select a job already
        # included with normal include.
        qual_gen = unit._gen_qualifiers(
            str(field), getattr(unit, str(field)), True)
        for qual in qual_gen:
            assert isinstance(qual, FieldQualifier)
            if qual.field != 'id':
                continue
            if isinstance(qual.matcher, PatternMatcher):
                for an_id in included_job_id:
                    if qual.matcher.match(an_id):
                        yield parent.warning(
                            unit, field, Problem.bad_reference,
                            warning.format(qual.matcher.pattern_text),
                            origin=qual.origin)
                        break
            elif isinstance(qual.matcher, OperatorMatcher):
                assert qual.matcher.op is operator.eq
                target_id = qual.matcher.value
                if target_id in included_job_id:
                    yield parent.warning(
                        unit, field, Problem.bad_reference,
                        warning.format(target_id),
                        origin=qual.origin)
            else:
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
    def mandatory_include(self):
        return self.get_record_value('mandatory_include')

    @property
    def bootstrap_include(self):
        return self.get_record_value('bootstrap_include')

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
    def certification_status_overrides(self):
        return self.get_record_value('certification-status-overrides')

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

    def get_bootstrap_job_ids(self):
        """Compute and return a set of job ids from bootstrap_include field."""
        job_ids = set()
        if self.bootstrap_include is None:
            return job_ids

        class V(Visitor):

            def visit_Text_node(visitor, node: Text):
                job_ids.add(self.qualify_id(node.text))

            def visit_Error_node(visitor, node: Error):
                logger.warning(_(
                    "unable to parse bootstrap_include: %s"), node.msg)

        V().visit(WordList.parse(self.bootstrap_include))
        return job_ids

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
        qual_list.extend([self.get_bootstrap_qualifier(excluding=True)])
        return CompositeQualifier(qual_list)

    def get_mandatory_qualifier(self):
        """
        Convert this test plan to an equivalent qualifier for job selection

        :returns:
            A CompositeQualifier corresponding to the contents of both
            the include and exclude fields.
        """
        qual_list = []
        qual_list.extend(self._gen_qualifiers('include', self.mandatory_include, True))
        return CompositeQualifier(qual_list)

    def get_bootstrap_qualifier(self, excluding=False):
        """
        Convert this test plan to an equivalent qualifier for job selection
        """
        qual_list = []
        if self.bootstrap_include is None:
            return CompositeQualifier(qual_list)
        field_origin = self.origin.just_line().with_offset(
            self.field_offset_map['bootstrap_include'])
        qual_list = [FieldQualifier(
            'id', OperatorMatcher(operator.eq, target_id), field_origin,
            not excluding) for target_id in self.get_bootstrap_job_ids()]
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
        from plainbox.impl.xparsers import Error
        from plainbox.impl.xparsers import ReErr, ReFixed, RePattern
        from plainbox.impl.xparsers import IncludeStmt
        from plainbox.impl.xparsers import IncludeStmtList
        from plainbox.impl.xparsers import Visitor

        outer_self = self

        class IncludeStmtVisitor(Visitor):

            def __init__(self):
                self.results = []  # (lineno_offset, field, matcher, error)

            def visit_IncludeStmt_node(self, node: IncludeStmt):
                if isinstance(node.pattern, ReErr):
                    matcher = None
                    error = node.pattern.exc
                elif isinstance(node.pattern, ReFixed):
                    target_id = outer_self.qualify_id(node.pattern.text)
                    matcher = OperatorMatcher(operator.eq, target_id)
                    error = None
                elif isinstance(node.pattern, RePattern):
                    text = node.pattern.text
                    # Ensure that pattern is surrounded by ^ and $
                    if text.startswith('^') and text.endswith('$'):
                        target_id_pattern = '^{}$'.format(
                            outer_self.qualify_id(text[1:-1]))
                    elif text.startswith('^'):
                        target_id_pattern = '^{}$'.format(
                            outer_self.qualify_id(text[1:]))
                    elif text.endswith('$'):
                        target_id_pattern = '^{}$'.format(
                            outer_self.qualify_id(text[:-1]))
                    else:
                        target_id_pattern = '^{}$'.format(
                            outer_self.qualify_id(text))
                    matcher = PatternMatcher(target_id_pattern)
                    error = None
                result = (node.lineno, 'id', matcher, error)
                self.results.append(result)

            def visit_Error_node(self, node: Error):
                # we're just faking an exception object here
                error = ValueError(node.msg)
                result = (node.lineno, 'id', None, error)
                self.results.append(result)

        visitor = IncludeStmtVisitor()
        visitor.visit(IncludeStmtList.parse(text, 0, 0))
        return visitor.results

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

    def qualify_pattern(self, pattern):
        """ qualify bare pattern (without ^ and $) """
        if pattern.startswith('^') and pattern.endswith('$'):
            return '^{}$'.format(self.qualify_id(pattern[1:-1]))
        elif pattern.startswith('^'):
            return '^{}$'.format(self.qualify_id(pattern[1:]))
        elif pattern.endswith('$'):
            return '^{}$'.format(self.qualify_id(pattern[:-1]))
        else:
            return '^{}$'.format(self.qualify_id(pattern))

    class Meta:

        name = 'test plan'

        class fields(SymbolDef):
            """
            Symbols for each field that a TestPlan can have
            """
            name = 'name'
            description = 'description'
            include = 'include'
            mandatory_include = 'mandatory_include'
            bootstrap_include = 'bootstrap_include'
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
            fields.mandatory_include: [
                NonEmptyPatternIntersectionValidator,
                NoBaseIncludeValidator,
            ],
            fields.bootstrap_include: [
                UntranslatableFieldValidator,
                NoBaseIncludeValidator,
                UnitReferenceValidator(
                    lambda unit: unit.get_bootstrap_job_ids(),
                    constraints=[
                        ReferenceConstraint(
                            lambda referrer, referee: referee.unit == 'job',
                            message=_("the referenced unit is not a job")),
                        ReferenceConstraint(
                            lambda referrer, referee: (
                                referee.plugin in ['local', 'resource']),
                            message=_("only local and resource jobs are "
                                      "allowed in bootstrapping_include"))])
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


class TestPlanUnitSupport:
    """
    Helper class that distills test plan data into more usable form

    This class serves to offload some of the code from :class:`TestPlanUnit`
    branch. It takes a single test plan unit and extracts all the interesting
    information out of it. Subsequently it exposes that data so that some
    methods on the test plan unit class itself can be implemented in an easier
    way.

    The key data to handle are obviously the ``include`` and ``exclude``
    fields. Those are used to come up with a qualifier object suitable for
    selecting jobs.

    The second key piece of data is obtained from the ``include`` field and
    from the ``category-overrides`` and ``certification-status-overrides``
    fields. From those fields we come up with a data structure that can be
    applied to a list of jobs to compute their override values.

    Some examples of how that works, given this test plan:
        >>> testplan = TestPlanUnit({
        ...     'include': '''
        ...         job-a certification-status=blocker, category-id=example
        ...         job-b certification-status=non-blocker
        ...         job-c
        ...     ''',
        ...     'exclude': '''
        ...         job-[x-z]
        ...     ''',
        ...     'category-overrides': '''
        ...         apply other-example to job-[bc]
        ...     ''',
        ...     'certification-status-overrides': '''
        ...         apply not-part-of-certification to job-c
        ...     ''',
        ...     })
        >>> support = TestPlanUnitSupport(testplan)

    We can look at the override list:

        >>> support.override_list
        ... # doctest: +NORMALIZE_WHITESPACE
        [('^job-[bc]$', [('category_id', 'other-example')]),
         ('^job-a$', [('certification_status', 'blocker'),
                      ('category_id', 'example')]),
         ('^job-b$', [('certification_status', 'non-blocker')]),
         ('^job-c$', [('certification_status', 'not-part-of-certification')])]

    And the qualifiers:

        >>> support.qualifier  # doctest: +NORMALIZE_WHITESPACE
        CompositeQualifier(qualifier_list=[FieldQualifier('id', OperatorMatcher(<built-in function eq>, 'job-a'), inclusive=True),
                                           FieldQualifier('id', OperatorMatcher(<built-in function eq>, 'job-b'), inclusive=True),
                                           FieldQualifier('id', OperatorMatcher(<built-in function eq>, 'job-c'), inclusive=True),
                                           FieldQualifier('id', PatternMatcher('^job-[x-z]$'), inclusive=False)])
    """

    def __init__(self, testplan):
        self.override_list = self._get_override_list(testplan)
        self.qualifier = self._get_qualifier(testplan)

    def _get_qualifier(self, testplan):
        qual_list = []
        qual_list.extend(
            self._get_qualifier_for(testplan, 'include', True))
        qual_list.extend(
            self._get_qualifier_for(testplan, 'exclude', False))
        return CompositeQualifier(qual_list)

    def _get_qualifier_for(self, testplan, field_name, inclusive):
        field_value = getattr(testplan, field_name)
        if field_value is None:
            return []
        field_origin = testplan.origin.just_line().with_offset(
            testplan.field_offset_map[field_name])
        matchers_gen = self._get_matchers(testplan, field_value)
        results = []
        for lineno_offset, matcher_field, matcher in matchers_gen:
            offset = field_origin.with_offset(lineno_offset)
            results.append(
                FieldQualifier(matcher_field, matcher, offset, inclusive))
        return results

    def _get_matchers(self, testplan, text):
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
        results = []

        class V(Visitor):

            def visit_IncludeStmt_node(self, node: IncludeStmt):
                if isinstance(node.pattern, ReFixed):
                    target_id = testplan.qualify_id(node.pattern.text)
                    matcher = OperatorMatcher(operator.eq, target_id)
                elif isinstance(node.pattern, RePattern):
                    pattern = testplan.qualify_pattern(node.pattern.text)
                    matcher = PatternMatcher(pattern)
                result = (node.lineno, 'id', matcher)
                results.append(result)

        V().visit(IncludeStmtList.parse(text, 0))
        return results

    def _get_override_list(
        self, testplan: TestPlanUnit
    ) -> "List[Tuple[str, List[Tuple[str, str]]]]":
        """
        Look at a test plan and compute the full (overall) override list.  The
        list contains information about each job selection pattern (fully
        qualified pattern) to a list of pairs ``(field, value)`` that ought to
        be applied to a :class:`JobState` object.

        The code below ensures that each ``field`` is an existing attribute of
        the job state object.

        .. note::
            The code below in *not* resilient to errors so make sure to
            validate the unit before starting with the helper.
        """
        override_map = collections.defaultdict(list)
        # ^^ Dict[str, Tuple[str, str]]
        for pattern, field_value_list in self._get_inline_overrides(testplan):
            override_map[pattern].extend(field_value_list)
        for pattern, field, value in self._get_category_overrides(testplan):
            override_map[pattern].append((field, value))
        for pattern, field, value in self._get_blocker_status_overrides(
                testplan):
            override_map[pattern].append((field, value))
        return sorted((key, field_value_list)
                      for key, field_value_list in override_map.items())

    def _get_category_overrides(
            self, testplan: TestPlanUnit
    ) -> "List[Tuple[str, str, str]]]":
        """
        Look at the category overrides and collect refined data about what
        overrides to apply. The result is represented as a list of tuples
        ``(pattern, field, value)`` where ``pattern`` is the string that
        describes the pattern, ``field`` is the field to which an override must
        be applied (but without the ``effective_`` prefix) and ``value`` is the
        overridden value.
        """
        override_list = []
        if testplan.category_overrides is None:
            return override_list

        class V(Visitor):

            def visit_FieldOverride_node(self, node: FieldOverride):
                category_id = testplan.qualify_id(node.value.text)
                pattern = r"^{}$".format(
                    testplan.qualify_id(node.pattern.text))
                override_list.append((pattern, 'category_id', category_id))

        V().visit(OverrideFieldList.parse(testplan.category_overrides))
        return override_list

    def _get_blocker_status_overrides(
            self, testplan: TestPlanUnit
    ) -> "List[Tuple[str, str, str]]]":
        """
        Look at the certification blocker status overrides and collect refined
        data about what overrides to apply. The result is represented as a list
        of tuples ``(pattern, field, value)`` where ``pattern`` is the string
        that describes the pattern, ``field`` is the field to which an override
        must be applied (but without the ``effective_`` prefix) and ``value``
        is the overridden value.
        """
        override_list = []
        if testplan.certification_status_overrides is None:
            return override_list

        class V(Visitor):

            def visit_FieldOverride_node(self, node: FieldOverride):
                blocker_status = node.value.text
                pattern = r"^{}$".format(
                    testplan.qualify_id(node.pattern.text))
                override_list.append(
                    (pattern, 'certification_status', blocker_status))

        V().visit(OverrideFieldList.parse(
            testplan.certification_status_overrides))
        return override_list

    def _get_inline_overrides(
            self, testplan: TestPlanUnit
    ) -> "List[Tuple[str, List[Tuple[str, str]]]]":
        """
        Look at the include field of a test plan and collect all of the in-line
        overrides. For an include statement that has any overrides they are
        collected into a list of tuples ``(field, value)`` and this list is
        subsequently packed into a tuple ``(pattern, field_value_list)``.
        """
        override_list = []
        if testplan.include is None:
            return override_list

        class V(Visitor):

            def visit_IncludeStmt_node(self, node: IncludeStmt):
                if not node.overrides:
                    return
                pattern = r"^{}$".format(
                    testplan.qualify_id(node.pattern.text))
                field_value_list = [
                    (override_exp.field.text.replace('-', '_'),
                     override_exp.value.text)
                    for override_exp in node.overrides]
                override_list.append((pattern, field_value_list))

        V().visit(IncludeStmtList.parse(testplan.include))
        return override_list
