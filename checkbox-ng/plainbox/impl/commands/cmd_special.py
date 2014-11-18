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
:mod:`plainbox.impl.commands.cmd_special` -- special sub-command
================================================================
"""
from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.cmd_checkbox import CheckBoxCommandMixIn


class SpecialCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Implementation of ``$ plainbox special``
    """

    def __init__(self, provider_loader, config_loader):
        self.provider_loader = provider_loader
        self.config_loader = config_loader

    def invoked(self, ns):
        from plainbox.impl.commands.inv_special import SpecialInvocation
        return SpecialInvocation(self.provider_loader, self.config_loader, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "special", help=_("special/internal commands"),
            prog="plainbox dev special")
        parser.set_defaults(command=self)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-j', '--list-jobs',
            help=_("list jobs instead of running them"),
            action="store_const", const="list-jobs", dest="special")
        group.add_argument(
            '-J', '--list-job-hashes',
            help=_("list jobs with cheksums instead of running them"),
            action="store_const", const="list-job-hashes", dest="special")
        group.add_argument(
            '-e', '--list-expressions',
            help=_("list all unique resource expressions"),
            action="store_const", const="list-expr", dest="special")
        group.add_argument(
            '-d', '--dot',
            help=_("print a graph of jobs instead of running them"),
            action="store_const", const="dep-graph", dest="special")
        parser.add_argument(
            '--dot-resources',
            # TRANSLATORS: please keep --dot untranslated
            help=_("show resource relationships (for --dot)"),
            action='store_true')
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
