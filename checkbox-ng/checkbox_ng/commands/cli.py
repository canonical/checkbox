# This file is part of Checkbox.
#
# Copyright 2013-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`checkbox_ng.commands.cli` -- Command line sub-command
===========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import SUPPRESS
from gettext import gettext as _
from logging import getLogger

from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.cmd_checkbox import CheckBoxCommandMixIn
from plainbox.impl.commands.inv_check_config import CheckConfigInvocation

from checkbox_ng.commands.newcli import CliInvocation2


logger = getLogger("checkbox.ng.commands.cli")


class CliCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Command for running tests using the command line UI.
    """
    gettext_domain = "checkbox-ng"

    def __init__(self, provider_loader, config_loader, settings):
        self.provider_loader = provider_loader
        self.config_loader = config_loader
        self.settings = settings

    def invoked(self, ns):
        # Run check-config, if requested
        if ns.check_config:
            retval = CheckConfigInvocation(self.config_loader).run()
            return retval
        return CliInvocation2(
            self.provider_loader, self.loader_config, ns, self.settings
        ).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(self.settings['subparser_name'],
                                       help=self.settings['subparser_help'])
        parser.set_defaults(command=self)
        parser.set_defaults(dry_run=False)
        parser.add_argument(
            "--check-config",
            action="store_true",
            help=_("run check-config"))
        group = parser.add_argument_group(title=_("user interface options"))
        parser.set_defaults(color=None)
        group.add_argument(
            '--no-color', dest='color', action='store_false', help=SUPPRESS)
        group.add_argument(
            '--non-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        group.add_argument(
            '--dont-suppress-output', action="store_true", default=False,
            help=_("don't suppress the output of certain job plugin types"))
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
