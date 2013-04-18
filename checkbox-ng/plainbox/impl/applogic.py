# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.impl.applogic` -- application logic
==================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from abc import ABCMeta, abstractmethod

import re


class IJobQualifier(metaclass=ABCMeta):
    """
    An opaque qualifier for a job definition.

    This is an abstraction for matching jobs definitions to names, patterns and
    other means of selecting jobs.
    """

    @abstractmethod
    def designates(self, job):
        """
        Check if this qualifier designates the specified
        :class:`plainbox.abc.IJobDefinition`

        :returns True: if the qualifier designates the specified job
        :returns False: otherwise
        """


class RegExpJobQualifier(IJobQualifier):
    """
    A JobQualifier that designates jobs by matching their name to a regular
    expression
    """

    def __init__(self, pattern):
        """
        Initialize a new RegExpJobQualifier with the specified pattern.
        """
        self._pattern = re.compile(pattern)
        self._pattern_text = pattern

    def designates(self, job):
        return self._pattern.match(job.name)

    def __repr__(self):
        return "<{0} pattern:{1!r}>".format(
            self.__class__.__name__, self._pattern_text)


class CompositeQualifier(IJobQualifier):
    """
    A JobQualifier that has qualifies jobs matching any inclusive qualifiers
    while not matching all of the exclusive qualifiers
    """

    def __init__(self, inclusive_qualifier_list, exclusive_qualifier_list):
        self.inclusive_qualifier_list = inclusive_qualifier_list
        self.exclusive_qualifier_list = exclusive_qualifier_list

    def designates(self, job):
        # First reject stuff that is excluded
        for qualifier in self.exclusive_qualifier_list:
            if qualifier.designates(job):
                return False
        # Then allow stuff that is included
        for qualifier in self.inclusive_qualifier_list:
            if qualifier.designates(job):
                return True
        # Lastly reject by default
        return False


def get_matching_job_list(job_list, qualifier):
    """
    Get a list of jobs that are designated by the specified qualifier.

    This is intended to be used with :class:`CompositeQualifier`
    but works with any :class:`IJobQualifier` subclass.
    """
    return [job for job in job_list if qualifier.designates(job)]
