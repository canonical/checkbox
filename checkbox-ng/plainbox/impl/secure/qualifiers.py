# This file is part of Checkbox.
#
# Copyright 2013, 2014 Canonical Ltd.
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
:mod:`plainbox.impl.secure.qualifiers` -- Job Qualifiers
========================================================

Qualifiers are callable objects that can be used to 'match' a job definition to
some set of rules.
"""

import abc
import functools
import itertools
import logging
import operator
import os
import re
import sre_constants

from plainbox.abc import IJobQualifier
from plainbox.i18n import gettext as _
from plainbox.impl import pod
from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.origin import UnknownTextSource


_logger = logging.getLogger("plainbox.secure.qualifiers")


class SimpleQualifier(IJobQualifier):
    """
    Abstract base class that implements common features of simple (non
    composite) qualifiers. This allows two concrete subclasses below to
    have share some code.
    """

    def __init__(self,  origin, inclusive=True):
        if origin is not None and not isinstance(origin, Origin):
            raise TypeError(_('argument {!a}, expected {}, got {}').format(
                'origin', Origin, type(origin)))
        if not isinstance(inclusive, bool):
            raise TypeError(_('argument {!a}, expected {}, got {}').format(
                'inclusive', bool, type(inclusive)))
        self._inclusive = inclusive
        self._origin = origin

    @property
    def inclusive(self):
        return self._inclusive

    @property
    def is_primitive(self):
        return True

    def designates(self, job):
        return self.get_vote(job) == self.VOTE_INCLUDE

    @abc.abstractmethod
    def get_simple_match(self, job):
        """
        Get a simple yes-or-no boolean answer if the given job matches the
        simple aspect of this qualifier. This method should be overridden by
        concrete subclasses.
        """

    def get_vote(self, job):
        """
        Get one of the ``VOTE_IGNORE``, ``VOTE_INCLUDE``, ``VOTE_EXCLUDE``
        votes that this qualifier associated with the specified job.

        :param job:
            A IJobDefinition instance that is to be visited
        :returns:
            * ``VOTE_INCLUDE`` if the job matches the simple qualifier concept
              embedded into this qualifier and this qualifier is **inclusive**.
            * ``VOTE_EXCLUDE`` if the job matches the simple qualifier concept
              embedded into this qualifier and this qualifier is **not
              inclusive**.
            * ``VOTE_IGNORE`` otherwise.

        .. versionadded: 0.5
        """
        if self.get_simple_match(job):
            if self.inclusive:
                return self.VOTE_INCLUDE
            else:
                return self.VOTE_EXCLUDE
        else:
            return self.VOTE_IGNORE

    def get_primitive_qualifiers(self):
        """
        Return a list of primitives that constitute this qualifier.

        :returns:
            A list of IJobQualifier objects that each is the smallest,
            indivisible entity. Here it just returns a list of one element,
            itself.

        .. versionadded: 0.5
        """
        return [self]

    @property
    def origin(self):
        """
        Origin of this qualifier

        This property can be used to trace the origin of a qualifier back to
        its definition point.
        """
        return self._origin


class RegExpJobQualifier(SimpleQualifier):
    """
    A JobQualifier that designates jobs by matching their id to a regular
    expression
    """

    # RegExp qualifier is instantiated many times. To speed up the process,
    # let's keep cache of compiled re object. (usually there are only a few of
    # those
    re_cache = dict()

    def __init__(self, pattern, origin, inclusive=True):
        """
        Initialize a new RegExpJobQualifier with the specified pattern.
        """
        super().__init__(origin, inclusive)
        try:
            if pattern not in self.re_cache:
                self.re_cache[pattern] = re.compile(pattern)
            self._pattern = self.re_cache[pattern]
        except sre_constants.error as exc:
            assert len(exc.args) == 1
            # XXX: This is a bit crazy but this lets us have identical error
            # messages across python3.2 all the way to 3.5. I really really
            # wish there was a better way at fixing this.
            exc.args = (re.sub(" at position \d+", "", exc.args[0]), )
            raise exc
        self._pattern_text = pattern

    def get_simple_match(self, job):
        """
        Check if the given job matches this qualifier.

        This method should not be called directly, it is an implementation
        detail of SimpleQualifier class.
        """
        return self._pattern.match(job.id) is not None

    @property
    def pattern_text(self):
        """
        text of the regular expression embedded in this qualifier
        """
        return self._pattern_text

    def __repr__(self):
        return "{0}({1!r}, inclusive={2})".format(
            self.__class__.__name__, self._pattern_text, self._inclusive)


class JobIdQualifier(SimpleQualifier):
    """
    A JobQualifier that designates a single job with a particular id
    """

    def __init__(self, id, origin, inclusive=True):
        super().__init__(origin, inclusive)
        self._id = id

    @property
    def id(self):
        """
        identifier to match
        """
        return self._id

    def get_simple_match(self, job):
        """
        Check if the given job matches this qualifier.

        This method should not be called directly, it is an implementation
        detail of SimpleQualifier class.
        """
        return self._id == job.id

    def __repr__(self):
        return "{0}({1!r}, inclusive={2})".format(
            self.__class__.__name__, self._id, self._inclusive)


class IMatcher(metaclass=abc.ABCMeta):
    """
    Interface for objects that perform some kind of comparison on a value
    """

    @abc.abstractmethod
    def match(self, value):
        """
        Match (or not) specified value

        :param value:
            value to match
        :returns:
            True if it matched, False otherwise
        """


@functools.total_ordering
class OperatorMatcher(IMatcher):
    """
    A matcher that applies a binary operator to the value
    """

    def __init__(self, op, value):
        self._op = op
        self._value = value

    @property
    def op(self):
        """
        the operator to use

        The operator is typically one of the functions from the ``operator``
        module. For example. operator.eq corresponds to the == python operator.
        """
        return self._op

    @property
    def value(self):
        """
        The right-hand-side value to apply to the operator

        The left-hand-side is the value that is passed to :meth:`match()`
        """
        return self._value

    def match(self, value):
        return self._op(self._value, value)

    def __repr__(self):
        return "{0}({1!r}, {2!r})".format(
            self.__class__.__name__, self._op, self._value)

    def __eq__(self, other):
        if isinstance(other, OperatorMatcher):
            return self.op == other.op and self.value == other.value
        else:
            return NotImplemented

    def __lt__(self, other):
        if isinstance(other, OperatorMatcher):
            if self.op < other.op:
                return True
            if self.value < other.value:
                return True
            return False
        else:
            return NotImplemented


class PatternMatcher(IMatcher):
    """
    A matcher that compares values by regular expression pattern
    """

    def __init__(self, pattern):
        self._pattern_text = pattern
        self._pattern = re.compile(pattern)

    @property
    def pattern_text(self):
        return self._pattern_text

    def match(self, value):
        return self._pattern.match(value) is not None

    def __repr__(self):
        return "{0}({1!r})".format(
            self.__class__.__name__, self._pattern_text)

    def __eq__(self, other):
        if isinstance(other, PatternMatcher):
            return self.pattern_text == other.pattern_text
        else:
            return NotImplemented

    def __lt__(self, other):
        if isinstance(other, PatternMatcher):
            return self.pattern_text < other.pattern_text
        else:
            return NotImplemented


class FieldQualifier(SimpleQualifier):
    """
    A SimpleQualifer that uses matchers to compare particular fields
    """

    def __init__(self, field, matcher, origin, inclusive=True):
        """
        Initialize a new FieldQualifier with the specified field, matcher and
        inclusive flag

        :param field:
            Name of the JobDefinition field to use
        :param matcher:
            A IMatcher object
        :param inclusive:
            Inclusive selection flag (default: True)
        """
        super().__init__(origin, inclusive)
        self._field = field
        self._matcher = matcher

    @property
    def field(self):
        """
        Name of the field to match
        """
        return self._field

    @field.setter
    def field(self, value):
        self._field = value

    @property
    def matcher(self):
        """
        The IMatcher-implementing object to use to check for the match
        """
        return self._matcher

    def get_simple_match(self, job):
        """
        Check if the given job matches this qualifier.

        This method should not be called directly, it is an implementation
        detail of SimpleQualifier class.
        """
        field_value = getattr(job, str(self._field))
        return self._matcher.match(field_value)

    def __repr__(self):
        return "{0}({1!r}, {2!r}, inclusive={3})".format(
            self.__class__.__name__, self._field, self._matcher,
            self._inclusive)


class CompositeQualifier(pod.POD):
    """
    A JobQualifier that has qualifies jobs matching any inclusive qualifiers
    while not matching all of the exclusive qualifiers
    """

    qualifier_list = pod.Field("qualifier_list", list, pod.MANDATORY)

    @property
    def is_primitive(self):
        return False

    def designates(self, job):
        return self.get_vote(job) == IJobQualifier.VOTE_INCLUDE

    def get_vote(self, job):
        """
        Get one of the ``VOTE_IGNORE``, ``VOTE_INCLUDE``, ``VOTE_EXCLUDE``
        votes that this qualifier associated with the specified job.

        :param job:
            A IJobDefinition instance that is to be visited
        :returns:
            * ``VOTE_INCLUDE`` if the job matches at least one qualifier voted
              to select it and no qualifiers voted to deselect it.
            * ``VOTE_EXCLUDE`` if at least one qualifier voted to deselect it
            * ``VOTE_IGNORE`` otherwise or if the list of qualifiers is empty.

        .. versionadded: 0.5
        """
        if self.qualifier_list:
            return min([
                qualifier.get_vote(job)
                for qualifier in self.qualifier_list])
        else:
            return IJobQualifier.VOTE_IGNORE

    def get_primitive_qualifiers(self):
        return get_flat_primitive_qualifier_list(self.qualifier_list)

    @property
    def origin(self):
        raise NonPrimitiveQualifierOrigin


IJobQualifier.register(CompositeQualifier)


class NonPrimitiveQualifierOrigin(Exception):
    """
    Exception raised when IJobQualifier.origin is meaningless as it is being
    requested on a non-primitive qualifier such as the CompositeQualifier
    """


def get_flat_primitive_qualifier_list(qualifier_list):
    return list(itertools.chain(*[
        qual.get_primitive_qualifiers()
        for qual in qualifier_list]))


def select_jobs(job_list, qualifier_list):
    """
    Select desired jobs.

    :param job_list:
        A list of JobDefinition objects
    :param qualifier_list:
        A list of IJobQualifier objects.
    :returns:
        A sub-list of JobDefinition objects, selected from job_list.
    """
    # Flatten the qualifier list, so that we can see the fine structure of
    # composite objects.
    flat_qualifier_list = get_flat_primitive_qualifier_list(qualifier_list)
    # Short-circuit if there are no jobs to select. Min is used later and this
    # will allow us to assume that the matrix is not empty.
    if not flat_qualifier_list:
        return []
    # Vote matrix, encodes the vote cast by a particular qualifier for a
    # particular job. Visually it's a two-dimensional array like this:
    #
    #   ^
    # q |
    # u |   X
    # a |
    # l |  ........
    # i |
    # f |             .
    # i | .
    # e |          .
    # r |
    #    ------------------->
    #                    job
    #
    # The vertical axis represents qualifiers from the flattened qualifier
    # list.  The horizontal axis represents jobs from job list. Dots represent
    # inclusion, X represents exclusion.
    #
    # The result of the select_jobs() function is a list of jobs that have at
    # least one inclusion and no exclusions. The resulting list is ordered by
    # increasing qualifier index.
    #
    # The algorithm implemented below is composed of two steps.
    #
    # The first step iterates over the vote matrix (row-major, meaning that we
    # visit all columns for each visit of one row) and constructs two
    # structures: a set of jobs that got VOTE_INCLUDE and a list of those jobs,
    # in the order of discovery. All VOTE_EXCLUDE votes are collected in
    # another set.
    #
    # The second step filters-out all items from the excluded job set from the
    # selected job list.
    #
    # The final complexity is O(N x M) + O(M), where N is the number of
    # qualifiers (flattened) and M is the number of jobs. The algorithm assumes
    # that set lookup is a O(1) operation which is true enough for python.
    #
    # A possible optimization would differentiate qualifiers that may select
    # more than one job and fall-back to the current implementation while
    # short-circuiting qualifiers that may select at most one job with a
    # separate set lookup. That would make the algorithm "mostly" linear in the
    # common case.
    #
    # As a separate feature, we might return a list of qualifiers that never
    # matched anything. That may be helpful for debugging.
    included_list = []
    included_set = set()
    excluded_set = set()

    def _handle_vote(qualifier, job):
        """
        Update list and sets of included/excluded jobs based on their related
        qualifiers.
        """
        vote = qualifier.get_vote(job)
        if vote == IJobQualifier.VOTE_INCLUDE:
            if job in included_set:
                return
            included_set.add(job)
            included_list.append(job)
        elif vote == IJobQualifier.VOTE_EXCLUDE:
            excluded_set.add(job)
        elif vote == IJobQualifier.VOTE_IGNORE:
            pass

    for qualifier in flat_qualifier_list:
        if (isinstance(qualifier, FieldQualifier) and
                qualifier.field == 'id' and
                isinstance(qualifier.matcher, OperatorMatcher) and
                qualifier.matcher.op == operator.eq):
            # optimize the super-common case where a qualifier refers to
            # a specific job by using the id_to_index_map to instantly
            # perform the requested operation on a single job
            for job in job_list:
                if job.id == qualifier.matcher.value:
                    _handle_vote(qualifier, job)
                    break
                elif job.template_id == qualifier.matcher.value:
                    # the qualifier matches the template id this job has been
                    # instantiated from, need to get the vote for this job
                    # based on its template_id field, not its id field
                    qualifier.field = "template_id"
                    _handle_vote(qualifier, job)
        else:
            for job in job_list:
                _handle_vote(qualifier, job)
    return [job for job in included_list
            if job not in excluded_set]
