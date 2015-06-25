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
:mod:`plainbox.impl.commands.run` -- run sub-command
====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import FileType, SUPPRESS

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.cmd_checkbox import CheckBoxCommandMixIn
from plainbox.impl.transport import get_all_transports


class RunCommand(PlainBoxCommand, CheckBoxCommandMixIn):

    def __init__(self, provider_loader, config_loader):
        self.provider_loader = provider_loader
        self.config_loader = config_loader

    def invoked(self, ns):
        from plainbox.impl.commands.inv_run import RunInvocation
        return RunInvocation(
            self.provider_loader, self.config_loader, ns, ns.color).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "run", help=_("run a test job"), prog="plainbox run")
        parser.set_defaults(command=self)
        group = parser.add_argument_group(title=_("user interface options"))
        parser.set_defaults(color=None)
        group.add_argument(
            '--no-color', dest='color', action='store_false', help=SUPPRESS)
        group.add_argument(
            '--non-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        group.add_argument(
            '-n', '--dry-run', action='store_true',
            help=_("don't really run most jobs"))
        group.add_argument(
            '--dont-suppress-output', action="store_true", default=False,
            help=_("don't suppress the output of certain job plugin types"))
        group = parser.add_argument_group(_("output options"))
        group.add_argument(
            '-f', '--output-format',
            default='2013.com.canonical.plainbox::text',
            metavar=_('FORMAT'),
            help=_('save test results in the specified FORMAT'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '-p', '--output-options', default='',
            metavar=_('OPTIONS'),
            help=_('comma-separated list of options for the export mechanism'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '-o', '--output-file', default='-',
            metavar=_('FILE'), type=FileType("wb"),
            help=_('save test results to the specified FILE'
                   ' (or to stdout if FILE is -)'))
        group.add_argument(
            '-t', '--transport',
            metavar=_('TRANSPORT'), choices=[_('?')] + list(
                get_all_transports().keys()),
            help=_('use TRANSPORT to send results somewhere'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '--transport-where',
            metavar=_('WHERE'),
            help=_('where to send data using the selected transport'))
        group.add_argument(
            '--transport-options',
            metavar=_('OPTIONS'),
            help=_('comma-separated list of key-value options (k=v) to '
                   'be passed to the transport'))
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
