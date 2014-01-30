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
import itertools
import os
import re

from plainbox.abc import IJobQualifier
from plainbox.impl.secure.rfc822 import FileTextSource
from plainbox.impl.secure.rfc822 import Origin
from plainbox.impl.secure.rfc822 import UnknownTextSource


class SimpleQualifier(IJobQualifier):
    """
    Abstract base class that implements common features of simple (non
    composite) qualifiers. This allows two concrete subclasses below to
    have share some code.
    """

    def __init__(self, inclusive=True):
        self._inclusive = inclusive

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


class RegExpJobQualifier(SimpleQualifier):
    """
    A JobQualifier that designates jobs by matching their name to a regular
    expression
    """

    def __init__(self, pattern, inclusive=True):
        """
        Initialize a new RegExpJobQualifier with the specified pattern.
        """
        super().__init__(inclusive)
        self._pattern = re.compile(pattern)
        self._pattern_text = pattern

    def get_simple_match(self, job):
        """
        Check if the given job matches this qualifier.

        This method should not be called directly, it is an implementation
        detail of SimpleQualifier class.
        """
        return self._pattern.match(job.name) is not None

    @property
    def pattern_text(self):
        """
        text of the regular expression embedded in this qualifier
        """
        return self._pattern_text

    def __repr__(self):
        return "{0}({1!r}, inclusive={2})".format(
            self.__class__.__name__, self._pattern_text, self._inclusive)


class NameJobQualifier(SimpleQualifier):
    """
    A JobQualifier that designates a single job with a particular name
    """

    def __init__(self, name, inclusive=True):
        super().__init__(inclusive)
        self._name = name

    def get_simple_match(self, job):
        """
        Check if the given job matches this qualifier.

        This method should not be called directly, it is an implementation
        detail of SimpleQualifier class.
        """
        return self._name == job.name

    def __repr__(self):
        return "{0}({1!r}, inclusive={2})".format(
            self.__class__.__name__, self._name, self._inclusive)


class CompositeQualifier(IJobQualifier):
    """
    A JobQualifier that has qualifies jobs matching any inclusive qualifiers
    while not matching all of the exclusive qualifiers
    """

    def __init__(self, qualifier_list):
        self.qualifier_list = qualifier_list

    @property
    def is_primitive(self):
        return False

    def designates(self, job):
        return self.get_vote(job) == self.VOTE_INCLUDE

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
            return self.VOTE_IGNORE

    def get_primitive_qualifiers(self):
        return get_flat_primitive_qualifier_list(self.qualifier_list)


# NOTE: using CompositeQualifier seems strange but it's a tested proven
# component so all we have to ensure is that we read the whitelist files
# correctly.
class WhiteList(CompositeQualifier):
    """
    A qualifier that understands checkbox whitelist files.

    A whitelist file is a plain text, line oriented file. Each line represents
    a regular expression pattern that can be matched against the name of a job.

    The file can contain simple shell-style comments that begin with the pound
    or hash key (#). Those are ignored. Comments can span both a fraction of a
    line as well as the whole line.

    For historical reasons each pattern has an implicit '^' and '$' prepended
    and appended (respectively) to the actual pattern specified in the file.
    """

    def __init__(self, pattern_list, name=None, origin=None):
        """
        Initialize a WhiteList object with the specified list of patterns.

        The patterns must be already mangled with '^' and '$'.
        """
        self._name = name
        self._origin = origin
        super(WhiteList, self).__init__(
            [RegExpJobQualifier(pattern) for pattern in pattern_list])

    def __repr__(self):
        return "<{} name:{!r}>".format(self.__class__.__name__, self.name)

    @property
    def name(self):
        """
        name of this WhiteList (might be None)
        """
        return self._name

    @name.setter
    def name(self, value):
        """
        set a new name for a WhiteList
        """
        self._name = value

    @property
    def origin(self):
        """
        origin object associated with this WhiteList (might be None)
        """
        return self._origin

    @classmethod
    def from_file(cls, pathname):
        """
        Load and initialize the WhiteList object from the specified file.

        :param pathname:
            file to load
        :returns:
            a fresh WhiteList object
        """
        pattern_list, max_lineno = cls._load_patterns(pathname)
        name = os.path.splitext(os.path.basename(pathname))[0]
        origin = Origin(FileTextSource(pathname), 1, max_lineno)
        return cls(pattern_list, name, origin)

    @classmethod
    def from_string(cls, text, *, filename=None, name=None, origin=None):
        """
        Load and initialize the WhiteList object from the specified string.

        :param text:
            full text of the whitelist
        :param filename:
            (optional, keyword-only) filename from which text was read from.
            This simulates a call to :meth:`from_file()` which properly
            computes the name and origin of the whitelist.
        :param name:
            (optional) name of the whitelist, only used if filename is not
            specified.
        :param origin:
            (optional) origin of the whitelist, only used if a filename is not
            specified.  If omitted a default origin value will be constructed
            out of UnknownTextSource instance
        :returns:
            a fresh WhiteList object

        The optional filename or a pair of name and origin arguments may be
        provided in order to have additional meta-data. This is typically
        needed when the :meth:`from_file()` method cannot be used as the caller
        already has the full text of the intended file available.
        """
        pattern_list, max_lineno = cls._parse_patterns(text)
        # generate name and origin if filename is provided
        if filename is not None:
            name = WhiteList.name_from_filename(filename)
            origin = Origin(FileTextSource(filename), 1, max_lineno)
        else:
            # otherwise generate origin if it's not specified
            if origin is None:
                origin = Origin(UnknownTextSource(), 1, max_lineno)
        return cls(pattern_list, name, origin)

    @classmethod
    def name_from_filename(cls, filename):
        """
        Compute the name of a whitelist based on the name
        of the file it is stored in.
        """
        return os.path.splitext(os.path.basename(filename))[0]

    @classmethod
    def _parse_patterns(cls, text):
        """
        Load whitelist patterns from the specified text

        :param text:
            string of text, including newlines, to parse
        :returns:
            (pattern_list, lineno) where lineno is the final line number
            (1-based) and pattern_list is a list of regular expression strings
            parsed from the whitelist.
        """
        pattern_list = []
        lineno = 0
        # Load the file
        for lineno, line in enumerate(text.splitlines(), 1):
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
            # Surround the pattern with ^ and $
            # so that it wont just match a part of the job name.
            regexp_pattern = r"^{pattern}$".format(pattern=line)
            # Accumulate patterns into the list
            pattern_list.append(regexp_pattern)
        return pattern_list, lineno

    @classmethod
    def _load_patterns(cls, pathname):
        """
        Load whitelist patterns from the specified file

        :param pathname:
            pathname of the file to load and parse
        :returns:
            (pattern_list, lineno) where lineno is the final line number
            (1-based) and pattern_list is a list of regular expression strings
            parsed from the whitelist.
        """
        with open(pathname, "rt", encoding="UTF-8") as stream:
            return cls._parse_patterns(stream.read())


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
    # composite objects, such as whitelists.
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
    # The result of the select_job() function is a list of jobs that have at
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
    # selected job list. For extra efficiency the algorithm operates on
    # integers representing the index of a particular job in job_list.
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
    for qualifier in flat_qualifier_list:
        for j_index, job in enumerate(job_list):
            vote = qualifier.get_vote(job)
            if vote == IJobQualifier.VOTE_INCLUDE:
                if j_index in included_set:
                    continue
                included_set.add(j_index)
                included_list.append(j_index)
            elif vote == IJobQualifier.VOTE_EXCLUDE:
                excluded_set.add(j_index)
            elif vote == IJobQualifier.VOTE_IGNORE:
                pass
    return [job_list[index] for index in included_list
            if index not in excluded_set]
