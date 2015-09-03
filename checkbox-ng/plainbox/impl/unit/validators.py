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
"""

import abc
import inspect
import itertools
import logging
import os
import shlex
import sys

from plainbox.i18n import gettext as _
from plainbox.i18n import ngettext
from plainbox.impl import pod
from plainbox.abc import IProvider1
from plainbox.impl.unit import get_accessed_parameters
from plainbox.impl.validation import Issue
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity

__all__ = [
    'CorrectFieldValueValidator',
    'DeprecatedFieldValidator',
    'FieldValidatorBase',
    'IFieldValidator',
    'PresentFieldValidator',
    'TemplateInvariantFieldValidator',
    'TemplateVariantFieldValidator',
    'TranslatableFieldValidator',
    'UniqueValueValidator',
    'UnitReferenceValidator',
    'UntranslatableFieldValidator',
]


logger = logging.getLogger("plainbox.unit")


def field2prop(field):
    """
    Convert a field to the property that is used to access that field

    :param field:
        A string or Symbol that represents the field
    :returns:
        Name of the property to access on the unit.
    """
    return str(field).replace('-', '_')


class UnitValidationContext(pod.POD):
    """
    Helper class for validating units in a bigger context

    This class has two purposes:

    1) to allow the validated object to see "everything" (other units)
    2) to allow validators to share temporary data structures
       and to prevent O(N**2) complexity of some checks.
    """

    provider_list = pod.Field(
        "list of all the providers", list, pod.MANDATORY,
        assign_filter_list=[pod.typed, pod.typed.sequence(IProvider1)])

    shared_cache = pod.Field(
        "cached computations", dict, initial_fn=dict,
        assign_filter_list=[pod.typed])

    def compute_shared(self, cache_key, func, *args, **kwargs):
        """
        Compute a shared helper.

        :param cache_key:
            Key to use to lookup the helper value
        :param func:
            Function that computes the helper value. The function is called
            with the context as the only argument
        :returns:
            Return value of func(self, *args, **kwargs) (possibly computed
            earlier).

        Compute something that can be shared by all the validation classes
        and units within one context. This allows certain validators to
        only compute expensive 'global' transformations of the context at most
        once.

        .. note::
            The caller is responsible for ensuring that ``args`` and ``kwargs``
            match the `cache_key` each time this function is called.
        """
        if cache_key not in self.shared_cache:
            self.shared_cache[cache_key] = func(*args, **kwargs)
        return self.shared_cache[cache_key]


class UnitFieldIssue(Issue):
    """
    Issue specific to a field of an Unit

    :attr unit:
        Name of the unit that the issue relates to
    :attr field:
        Name of the field within the unit
    """

    def __init__(self, message, severity, kind, origin, unit, field):
        super().__init__(message, severity, kind, origin)
        self.unit = unit
        self.field = field

    def __repr__(self):
        return (
            "{}(message={!r}, severity={!r}, kind={!r}, origin={!r}"
            " unit={!r}, field={!r})"
        ).format(
            self.__class__.__name__,
            self.message, self.severity, self.kind, self.origin,
            self.unit, self.field)


class MultiUnitFieldIssue(Issue):
    """
    Issue involving multiple units.

    :attr unit_list:
        Name of the unit that the issue relates to
    :attr field:
        Name of the field within the unit
    """

    def __init__(self, message, severity, kind, origin, unit_list, field):
        super().__init__(message, severity, kind, origin)
        self.unit_list = unit_list
        self.field = field

    def __repr__(self):
        return (
            "{}(message={!r}, severity={!r}, kind={!r}, origin={!r}"
            " unit_list={!r}, field={!r})"
        ).format(
            self.__class__.__name__,
            self.message, self.severity, self.kind, self.origin,
            self.unit_list, self.field)


class IFieldValidator(metaclass=abc.ABCMeta):
    """
    Interface for all :class:`Unit` field validators.

    Instances of this class participate in the validation process.
    """

    @abc.abstractmethod
    def __init__(self, **kwargs):
        """
        Initialize the validator to check the specified field.

        :param kwargs:
            Any additional arguments associated with the validator
            that were defined on the UnitValidator
        """

    def check(self, parent, unit, field):
        """
        Perform the check associated with a specific field

        :param parent:
            The :class:`UnitValidator` that this validator cooperates with
        :param unit:
            The :class:`Unit` to validate
        :param field:
            The field to check, this may be a Symbol
        :returns:
            None

        This method doesn't raise any exceptions nor returns error values.
        Instead it is expected to use the :meth:`UnitValidator.report_issue()`
        family of methods (including error, warning and advice) to report
        detected problems
        """

    def check_in_context(self, parent, unit, field, context):
        """
        Perform the check associated with a specific field in a known context

        :param parent:
            The :class:`UnitValidator` that this validator cooperates with
        :param unit:
            The :class:`Unit` to validate
        :param field:
            The field to check, this may be a Symbol
        :param context:
            The :class:`UnitValidationContext` to use
        :returns:
            None

        This method doesn't raise any exceptions nor returns error values.
        Instead it is expected to use the :meth:`UnitValidator.report_issue()`
        family of methods (including error, warning and advice) to report
        detected problems
        """


class FieldValidatorBase(IFieldValidator):
    """
    Base validator that implements no checks of any kind
    """

    def __init__(self, message=None):
        self.message = message

    def check(self, parent, unit, field):
        return ()

    def check_in_context(self, parent, unit, field, context):
        return ()


class CorrectFieldValueValidator(FieldValidatorBase):
    """
    Validator ensuring that a field value is correct according to some criteria

    This validator simply ensures that a value of a field (as accessed through
    a field-property) matches a predefined criteria. The criteria can
    be specified externally which makes this validator very flexible.
    """
    default_severity = Severity.error
    default_kind = Problem.wrong

    def __init__(self, correct_fn, kind=None, severity=None, message=None,
                 onlyif=None):
        """
        correct_fn:
            A function that checks if the value is correct or not. If it
            returns False then an issue is reported in accordance with other
            arguments.  It is called either as ``correct_fn(value)`` or
            ``correct_fn(value, unit)`` based on the number of accepted
            arguments.
        kind:
            Kind of issue to report. By default this is Problem.wrong
        severity:
            Severity of the issue to report. By default this is Severity.error
        message:
            Customized error message. This message will be used to report the
            issue if the validation fails. By default it is derived from the
            specified issue ``kind`` by :meth:`UnitValidator.explain()`.
        onlyif:
            An optional function that checks if this validator should be
            applied or not. The function is called with the `unit` as the only
            argument.  If it returns True then the validator proceeds to
            perform its check.
        """
        super().__init__(message)
        if sys.version_info[:2] >= (3, 5):
            has_two_args = len(inspect.signature(correct_fn).parameters) == 2
        else:
            has_two_args = len(inspect.getargspec(correct_fn).args) == 2
        self.correct_fn = correct_fn
        self.correct_fn_needs_unit = has_two_args
        self.kind = kind or self.default_kind
        self.severity = severity or self.default_severity
        self.onlyif = onlyif

    def check(self, parent, unit, field):
        # Skip this validator if onlyif says we should do so
        if self.onlyif is not None and not self.onlyif(unit):
            return
        # Look up the value
        value = getattr(unit, field2prop(field))
        try:
            if self.correct_fn_needs_unit:
                is_correct = self.correct_fn(value, unit)
            else:
                is_correct = self.correct_fn(value)
        except Exception as exc:
            yield parent.report_issue(
                unit, field, self.kind, self.severity,
                self.message or str(exc))
        else:
            # Report an issue if the correctness check failed
            if not is_correct:
                yield parent.report_issue(
                    unit, field, self.kind, self.severity, self.message)


class PresentFieldValidator(CorrectFieldValueValidator):
    """
    Validator ensuring that a field has a value

    This validator simply ensures that a value of a field (as accessed through
    a field-property) is not None. It is useful for simple checks for required
    fields.
    """
    default_kind = Problem.missing

    def __init__(self, kind=None, severity=None, message=None, onlyif=None):
        """
        correct_fn:
            A function that checks if the value is correct or not. If it
            returns False then an issue is reported in accordance with other
            arguments
        kind:
            Kind of issue to report. By default this is Problem.missing
        severity:
            Severity of the issue to report. By default this is Severity.error
        message:
            Customized error message. This message will be used to report the
            issue if the validation fails. By default it is derived from the
            specified issue ``kind`` by :meth:`UnitValidator.explain()`.
        """
        correct_fn = lambda value: value is not None
        super().__init__(correct_fn, kind, severity, message, onlyif)


class UselessFieldValidator(CorrectFieldValueValidator):
    """
    Validator ensuring that no value is specified to a field in certain context

    The context should be encoded by passing the onlyif argument which can
    inspect the unit and determine if a field is useless or not.
    """

    default_kind = Problem.useless
    default_severity = Severity.warning

    def __init__(self, kind=None, severity=None, message=None, onlyif=None):
        """
        correct_fn:
            A function that checks if the value is correct or not. If it
            returns False then an issue is reported in accordance with other
            arguments
        kind:
            Kind of issue to report. By default this is Problem.useless
        severity:
            Severity of the issue to report. By default this is
            Severity.warning
        message:
            Customized error message. This message will be used to report the
            issue if the validation fails. By default it is derived from the
            specified issue ``kind`` by :meth:`UnitValidator.explain()`.
        """
        correct_fn = lambda value: value is None
        super().__init__(correct_fn, kind, severity, message, onlyif)


class DeprecatedFieldValidator(FieldValidatorBase):
    """
    Validator ensuring that deprecated field is not used (passed a value)
    """

    def check(self, parent, unit, field):
        # This is not a using a property so that we can remove the property but
        # still check that the field is not being used.
        if unit.get_record_value(field) is not None:
            yield parent.report_issue(
                unit, field, Problem.deprecated, Severity.advice, self.message)


class TranslatableFieldValidator(FieldValidatorBase):
    """
    Validator ensuring that a field is marked as translatable

    The validator can be customized by passing the following keyword arguments:

    message:
        Customized error message. This message will be used to report the
        issue if the validation fails. By default it is derived from
        ``Problem.expected_i18n`` by :meth:`UnitValidator.explain()`.
    """

    def check(self, parent, unit, field):
        if (unit.virtual is False
                and unit.get_record_value(field) is not None
                and not unit.is_translatable_field(field)):
            yield parent.warning(unit, field, Problem.expected_i18n)


class UntranslatableFieldValidator(FieldValidatorBase):
    """
    Validator ensuring that a field is not marked as translatable

    The validator can be customized by passing the following keyword arguments:

    message:
        Customized error message. This message will be used to report the
        issue if the validation fails. By default it is derived from
        ``Problem.unexpected_i18n`` by :meth:`UnitValidator.explain()`.
    """

    def check(self, parent, unit, field):
        if (unit.get_record_value(field)
                and unit.is_translatable_field(field)):
            yield parent.warning(unit, field, Problem.unexpected_i18n)


class TemplateInvariantFieldValidator(FieldValidatorBase):
    """
    Validator ensuring that a field value doesn't depend on a template resource
    """

    def check(self, parent, unit, field):
        # Non-parametric units are always valid
        if unit.is_parametric:
            value = unit._data.get(field)
            # No value? No problem!
            if value is None:
                return
            param_set = get_accessed_parameters(value)
            # Invariant fields cannot depend on any parameters
            if len(param_set) != 0:
                yield parent.error(unit, field, Problem.variable, self.message)


class TemplateVariantFieldValidator(FieldValidatorBase):
    """
    Validator ensuring that a field value does depend on a template resource

    In addition, the actual value template is checked to ensure that each
    parameter it references is defined in the particular unit being validated.
    """

    def check(self, parent, unit, field):
        # Non-parametric units are always valid
        if unit.is_parametric:
            value = unit._data.get(field)
            # No value? No problem!
            if value is not None:
                param_set = get_accessed_parameters(value)
                # Variant fields must depend on some parameters
                if len(param_set) == 0:
                    yield parent.error(
                        unit, field, Problem.constant, self.message)
                # Each parameter must be present in the unit
                for param_name in param_set:
                    if param_name not in unit.parameters:
                        message = _(
                            "reference to unknown parameter {!r}"
                        ).format(param_name)
                        yield parent.error(
                            unit, field, Problem.unknown_param, message)


class ShellProgramValidator(FieldValidatorBase):
    """
    Validator ensuring that a field value looks like a valid shell program

    This validator can help catch simple mistakes detected by a
    shell-compatible lexer. It doesn't support the heredoc syntax and it
    silently ignores fields that have '<<' anywhere in the value.
    """

    def check(self, parent, unit, field):
        # Look up the value
        value = getattr(unit, field2prop(field))
        if value is not None:
            if '<<' in value:
                # TODO: implement heredoc-aware shlex parser
                # and use it to validate the input
                pass
            else:
                lex = shlex.shlex(value, posix=True)
                token = None
                try:
                    for token in lex:
                        pass
                except ValueError as exc:
                    if token is not None:
                        yield parent.error(
                            unit, field, Problem.syntax_error,
                            "{}, near {!r}".format(exc, token),
                            offset=lex.lineno - 1)
                    else:
                        yield parent.error(
                            unit, field, Problem.syntax_error, str(exc),
                            offset=lex.lineno - 1)


def compute_value_map(context, field):
    """
    Compute support data structure

    :param context:
        The :class:`UnitValidationContext` instance that this data is computed
        for. It is used to discover a list of providers
    :returns:
        A dictionary mapping from all the existing values of a specific field
        (that is being validated) to a list of units that have that value in
        that field.
    """
    value_map = {}
    all_units = itertools.chain(
        *(provider.unit_list for provider in context.provider_list))
    for unit in all_units:
        try:
            value = getattr(unit, field2prop(field))
        except AttributeError:
            continue
        if value not in value_map:
            value_map[value] = [unit]
        else:
            value_map[value].append(unit)
    return value_map


class UniqueValueValidator(FieldValidatorBase):
    """
    Validator that checks if a value of a specific field is unique

    This validator only works in context mode where it ensures that all the
    units in all providers present in the context have an unique value for a
    specific field.

    This is mostly applicable to the 'id' field but other fields may be used.

    The algorithm has O(1) complexity (where N is the number of units) per unit
    which translates to O(N) cost for the whole context.
    """

    def check_in_context(self, parent, unit, field, context):
        value_map = context.compute_shared(
            "field_value_map[{}]".format(field),
            compute_value_map, context, field)
        value = getattr(unit, field2prop(field))
        units_with_this_value = value_map[value]
        n = len(units_with_this_value)
        if n > 1:
            # come up with unit_list where this unit is always at the front
            unit_list = list(units_with_this_value)
            unit_list = sorted(
                unit_list,
                key=lambda a_unit: 0 if a_unit is unit
                else unit_list.index(a_unit) + 1)
            yield parent.error(
                unit_list, field, Problem.not_unique, ngettext(
                    "clashes with {0} other unit",
                    "clashes with {0} other units", n - 1
                ).format(n - 1) + ', look at: ' + ', '.join(
                    # XXX: the relative_to is a hack, ideally we would
                    # allow the UI to see the fine structure of the error
                    # message and pass appropriate path to relative_to()
                    str(other_unit.origin.relative_to(os.getcwd()))
                    for other_unit in units_with_this_value
                    if other_unit is not unit))


class ReferenceConstraint:
    """
    Description of a constraint on a unit reference

    :attr constraint_fn:
        A function fn(referrer, referee) that describes the constraint.
        The function must return True in order for the constraint to hold.
    :attr message:
        Message that should be reported when the constraint fails to hold
    :attr onlyif:
        An (optional) function fn(referrer, referee) that checks if the
        constraint should be checked or not. It must return True for the
        ``constraint_fn`` to make sense.
    """

    def __init__(self, constraint_fn, message, *, onlyif=None):
        self.constraint_fn = constraint_fn
        self.onlyif = onlyif
        self.message = message


class UnitReferenceValidator(FieldValidatorBase):
    """
    Validator that checks if a field references another unit

    This validator only works in context mode where it ensures that all the
    units in all providers present in the context have an unique value for a
    specific field.

    The algorithm has O(1) complexity (where N is the number of units) per unit
    which translates to O(N) cost for the whole context.
    """

    def __init__(self, get_references_fn, constraints=None, message=None):
        super().__init__(message)
        self.get_references_fn = get_references_fn
        if constraints is None:
            constraints = ()
        self.constraints = constraints

    def check_in_context(self, parent, unit, field, context):
        id_map = context.compute_shared(
            "field_value_map[id]", compute_value_map, context, 'id')
        try:
            value_list = self.get_references_fn(unit)
        except Exception as exc:
            yield parent.error(unit, field, Problem.wrong, str(exc))
            value_list = None
        if value_list is None:
            value_list = []
        elif not isinstance(value_list, (list, tuple, set)):
            value_list = [value_list]
        for unit_id in value_list:
            try:
                units_with_this_id = id_map[unit_id]
            except KeyError:
                # zero is wrong, broken reference
                yield parent.error(
                    unit, field, Problem.bad_reference,
                    self.message or _(
                        "unit {!a} is not available"
                    ).format(unit_id))
                continue
            n = len(units_with_this_id)
            if n == 1:
                # one is exactly right, let's see if it's good
                referrer = unit
                referee = units_with_this_id[0]
                for constraint in self.constraints:
                    if constraint.onlyif is not None and not constraint.onlyif(
                            referrer, referee):
                        continue
                    if not constraint.constraint_fn(referrer, referee):
                        yield parent.error(
                            unit, field, Problem.bad_reference,
                            self.message or constraint.message
                            or _("referee constraint failed"))
            elif n > 1:
                # more than one is also good, which one are we targeting?
                yield parent.error(
                    unit, field, Problem.bad_reference,
                    self.message or _(
                        "multiple units with id {!a}: {}"
                    ).format(
                        unit_id, ', '.join(
                            # XXX: the relative_to is a hack, ideally we would
                            # allow the UI to see the fine structure of the
                            # error message and pass appropriate path to
                            # relative_to()
                            str(other_unit.origin.relative_to(os.getcwd()))
                            for other_unit in units_with_this_id)))
