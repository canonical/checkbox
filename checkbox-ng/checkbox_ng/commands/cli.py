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

from gettext import gettext as _
from logging import getLogger
import argparse

from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.check_config import CheckConfigInvocation
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn


logger = getLogger("checkbox.ng.commands.cli")


class CliCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Command for running tests using the command line UI.
    """
    gettext_domain = "checkbox-ng"

    def __init__(self, provider_list, config, settings):
        self.provider_list = provider_list
        self.config = config
        self.settings = settings

    def invoked(self, ns):
        # Run check-config, if requested
        if ns.check_config:
            retval = CheckConfigInvocation(self.config).run()
            return retval
        if ns.new_ui:
            from checkbox_ng.commands.newcli import CliInvocation2
            return CliInvocation2(self.provider_list, self.config, ns,
                                  self.settings).run()
        else:
            from checkbox_ng.commands.oldcli import CliInvocation
            return CliInvocation(self.provider_list, self.config,
                                 self.settings, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(self.settings['subparser_name'],
                                       help=self.settings['subparser_help'])
        parser.set_defaults(command=self)
        parser.set_defaults(dry_run=False, new_ui=True)
        parser.add_argument(
            '--new-ui', help=argparse.SUPPRESS, action='store_true')
        parser.add_argument(
            '--old-ui', dest='new_ui', help=argparse.SUPPRESS,
            action='store_false')
        parser.add_argument(
            "--check-config",
            action="store_true",
            help=_("run check-config"))
        parser.add_argument(
            '--not-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
