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

from plainbox.i18n import gettext as _
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.qualifiers import select_jobs

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
        logger.debug("_get_matching_job_list(%r, %r)", ns, job_list)
        qualifier_list = []
        # Add whitelists
        for whitelist_file in ns.whitelist:
            try:
                qualifier = WhiteList.from_string(
                    whitelist_file.read(), filename=whitelist_file.name)
            except Exception as exc:
                logger.warning(
                    _("Unable to load whitelist %r: %s"), whitelist_file, exc)
            else:
                qualifier_list.append(qualifier)
        # Add all the --include jobs
        for pattern in ns.include_pattern_list:
            try:
                qualifier = RegExpJobQualifier(
                    '^{}$'.format(pattern), inclusive=True)
            except Exception as exc:
                logger.warning(
                    _("Incorrect pattern %r: %s"), pattern, exc)
            else:
                qualifier_list.append(qualifier)
        # Add all the --exclude jobs
        for pattern in ns.exclude_pattern_list:
            try:
                qualifier = RegExpJobQualifier(
                    '^{}$'.format(pattern), inclusive=False)
            except Exception as exc:
                logger.warning(
                    _("Incorrect pattern %r: %s"), pattern, exc)
            else:
                qualifier_list.append(qualifier)
        logger.debug("select_jobs(%r, %r)", job_list, qualifier_list)
        return select_jobs(job_list, qualifier_list)


class CheckBoxCommandMixIn:
    """
    Mix-in class for plainbox commands that want to discover and load checkbox
    jobs
    """

    def enhance_parser(self, parser):
        """
        Add common options for job selection to an existing parser
        """
        group = parser.add_argument_group(title=_("job definition options"))
        group.add_argument(
            '-i', '--include-pattern', action="append",
            metavar=_('PATTERN'), default=[], dest='include_pattern_list',
            # TRANSLATORS: this is in imperative form
            help=_("include jobs matching the given regular expression"))
        group.add_argument(
            '-x', '--exclude-pattern', action="append",
            metavar=_("PATTERN"), default=[], dest='exclude_pattern_list',
            # TRANSLATORS: this is in imperative form
            help=_("exclude jobs matching the given regular expression"))
        # TODO: Find a way to handle the encoding of the file
        group.add_argument(
            '-w', '--whitelist',
            action="append",
            metavar=_("WHITELIST"),
            default=[],
            type=FileType("rt"),
            # TRANSLATORS: this is in imperative form
            help=_("load whitelist containing run patterns"))
