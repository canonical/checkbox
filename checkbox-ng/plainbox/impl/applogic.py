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

import os
import re

from plainbox.abc import IJobQualifier
from plainbox.abc import IJobResult
from plainbox.impl import config
from plainbox.impl.result import MemoryJobResult


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

    @property
    def pattern_text(self):
        """
        text of the regular expression embedded in this qualifier
        """
        return self._pattern_text

    def designates(self, job):
        return self._pattern.match(job.name)

    def __repr__(self):
        return "<{0} pattern:{1!r}>".format(
            self.__class__.__name__, self._pattern_text)


class NameJobQualifier(IJobQualifier):
    """
    A JobQualifier that designates a single job with a particular name
    """

    def __init__(self, name):
        self._name = name

    def designates(self, job):
        return self._name == job.name

    def __repr__(self):
        return "<{0} name:{1!r}>".format(
            self.__class__.__name__, self._name)


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

    def __init__(self, pattern_list, name=None):
        """
        Initialize a whitelist object with the specified list of patterns.

        The patterns must be already mangled with '^' and '$'.
        """
        inclusive = [RegExpJobQualifier(pattern) for pattern in pattern_list]
        exclusive = ()
        super(WhiteList, self).__init__(inclusive, exclusive)
        self._name = name

    def __repr__(self):
        return "<{} name:{!r}>".format(self.__class__.__name__, self.name)

    @property
    def name(self):
        """
        name of this WhiteList (might be None)
        """
        return self._name

    @classmethod
    def from_file(cls, pathname):
        """
        Load and initialize the WhiteList object from the specified file.

        :param pathname: file to load
        :returns: a fresh WhiteList object
        """
        pattern_list = cls._load_patterns(pathname)
        name = os.path.splitext(os.path.basename(pathname))[0]
        return cls(pattern_list, name=name)

    @classmethod
    def _load_patterns(self, pathname):
        """
        Load whitelist patterns from the specified file
        """
        pattern_list = []
        # Load the file
        with open(pathname, "rt", encoding="UTF-8") as stream:
            for line in stream:
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
        return pattern_list


def get_matching_job_list(job_list, qualifier):
    """
    Get a list of jobs that are designated by the specified qualifier.

    This is intended to be used with :class:`CompositeQualifier`
    but works with any :class:`IJobQualifier` subclass.
    """
    return [job for job in job_list if qualifier.designates(job)]


def run_job_if_possible(session, runner, config, job):
    """
    Coupling point for session, runner, config and job

    :returns: (job_state, job_result)
    """
    job_state = session.job_state_map[job.name]
    if job_state.can_start():
        job_result = runner.run_job(job, config)
    else:
        # Set the outcome of jobs that cannot start to
        # OUTCOME_NOT_SUPPORTED _except_ if any of the inhibitors point to
        # a job with an OUTCOME_SKIP outcome, if that is the case mirror
        # that outcome. This makes 'skip' stronger than 'not-supported'
        outcome = IJobResult.OUTCOME_NOT_SUPPORTED
        for inhibitor in job_state.readiness_inhibitor_list:
            if inhibitor.cause != inhibitor.FAILED_DEP:
                continue
            related_job_state = session.job_state_map[
                inhibitor.related_job.name]
            if related_job_state.result.outcome == IJobResult.OUTCOME_SKIP:
                outcome = IJobResult.OUTCOME_SKIP
        job_result = MemoryJobResult({
            'outcome': outcome,
            'comments': job_state.get_readiness_description()
        })
    assert job_result is not None
    session.update_job_result(job, job_result)
    return job_state, job_result


class PlainBoxConfig(config.Config):
    """
    Configuration for PlainBox itself
    """

    secure_id = config.Variable(
        section="sru",
        help_text="Secure ID of the system",
        validator_list=[config.PatternValidator(
            r"^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$"
        )])

    # TODO: Add a validator to check if URL looks fine
    c3_url = config.Variable(
        section="sru",
        help_text="URL of the certification website",
        default="https://certification.canonical.com/submissions/submit/")

    fallback_file = config.Variable(
        section="sru",
        help_text="Location of the fallback file")

    whitelist = config.Variable(
        section="sru",
        help_text="Optional whitelist with which to run SRU testing")

    environment = config.Section(
        help_text="Environment variables for scripts and jobs")

    default_provider = config.Variable(
        section="common",
        help_text="Name of the default provider to use",
        validator_list=[
            config.ChoiceValidator(['auto', 'src', 'deb', 'stub', 'ihv'])],
        default="auto")

    class Meta:

        # TODO: properly depend on xdg and use real code that also handles
        # XDG_CONFIG_HOME.
        filename_list = [
            '/etc/xdg/plainbox.conf',
            os.path.expanduser('~/.config/plainbox.conf')]
