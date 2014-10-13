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
:mod:`plainbox.impl.commands.cmd_checkbox` -- mix-in for checkbox commands
==========================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import FileType
from logging import getLogger

from plainbox.i18n import gettext as _


logger = getLogger("plainbox.commands.checkbox")


class CheckBoxCommandMixIn:
    """
    Mix-in class for plainbox commands that want to discover and load checkbox
    jobs
    """

    def enhance_parser(self, parser):
        """
        Add common options for job selection to an existing parser
        """
        group = parser.add_argument_group(title=_("test selection options"))
        group.add_argument(
            '-T', '--test-plan',
            action="store",
            metavar=_("TEST-PLAN-ID"),
            default=None,
            # TRANSLATORS: this is in imperative form
            help=_("load the specified test plan"))
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
