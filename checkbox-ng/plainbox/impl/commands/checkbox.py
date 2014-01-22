# This file is part of Checkbox.
#
# Copyright 2012-2013 Canonical Ltd.
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
:mod:`plainbox.impl.commands.checkbox` -- mix-in for checkbox commands
======================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import FileType
from logging import getLogger
import itertools
import re


logger = getLogger("plainbox.commands.checkbox")


class CheckBoxInvocationMixIn:

    def __init__(self, provider_list):
        self.provider_list = provider_list

    def get_job_list(self, ns):
        """
        Load and return a list of JobDefinition instances
        """
        return list(
            itertools.chain(*[
                p.load_all_jobs()[0] for p in self.provider_list]))

    def _get_matching_job_list(self, ns, job_list):
        # Find jobs that matched patterns
        matching_job_list = []
        # Pre-seed the include pattern list with data read from
        # the whitelist file.
        if ns.whitelist:
            for whitelist in ns.whitelist:
                ns.include_pattern_list.extend([
                    pattern.strip()
                    for pattern in whitelist.readlines()])
        # Decide which of the known jobs to include
        if ns.exclude_pattern_list:
            for pattern in ns.exclude_pattern_list:
                # Reject all jobs that match any of the exclude
                # patterns, matching strictly from the start to
                # the end of the line.
                try:
                    regexp_pattern = re.compile(
                        r"^{pattern}$".format(pattern=pattern))
                except re.error:
                    logger.warning("Invalid exclude pattern: %s", pattern)
                    continue
                for job in job_list:
                    if regexp_pattern.match(job.name):
                        job_list.remove(job)
        if ns.include_pattern_list:
            for pattern in ns.include_pattern_list:
                # Accept (include) all job that matches
                # any of include patterns, matching strictly
                # from the start to the end of the line.
                try:
                    regexp_pattern = re.compile(
                        r"^{pattern}$".format(pattern=pattern))
                except re.error:
                    logger.warning("Invalid include pattern: %s", pattern)
                    continue
                for job in job_list:
                    if regexp_pattern.match(job.name):
                        matching_job_list.append(job)
        return matching_job_list


class CheckBoxCommandMixIn:
    """
    Mix-in class for plainbox commands that want to discover and load checkbox
    jobs
    """

    def enhance_parser(self, parser):
        """
        Add common options for job selection to an existing parser
        """
        group = parser.add_argument_group(title="job definition options")
        group.add_argument(
            '-i', '--include-pattern', action="append",
            metavar='PATTERN', default=[], dest='include_pattern_list',
            help=("Run jobs matching the given regular expression. Matches "
                  "from the start to the end of the line."))
        group.add_argument(
            '-x', '--exclude-pattern', action="append",
            metavar="PATTERN", default=[], dest='exclude_pattern_list',
            help=("Do not run jobs matching the given regular expression. "
                  "Matches from the start to the end of the line."))
        # TODO: Find a way to handle the encoding of the file
        group.add_argument(
            '-w', '--whitelist',
            action="append",
            metavar="WHITELIST",
            type=FileType("rt"),
            help="Load whitelist containing run patterns")
