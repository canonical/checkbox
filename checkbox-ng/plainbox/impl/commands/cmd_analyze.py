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
:mod:`plainbox.impl.commands.cmd_analyze` -- analyze sub-command
================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from logging import getLogger

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.cmd_checkbox import CheckBoxCommandMixIn


logger = getLogger("plainbox.commands.analyze")


class AnalyzeCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Implementation of ``$ plainbox dev analyze``
    """

    def __init__(self, provider_loader, config_loader):
        self.provider_loader = provider_loader
        self.config_loader = config_loader

    def invoked(self, ns):
        from plainbox.impl.commands.inv_analyze import AnalyzeInvocation
        return AnalyzeInvocation(
            self.provider_loader, self.config_loader, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "analyze", help=_("analyze how selected jobs would be executed"),
            prog="plainbox dev analyze")
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '-l', '--run-local',
            action='store_true', dest='run_local',
            help=_('run all selected local jobs, required to see true data'))
        group.add_argument(
            '-L', '--skip-local',
            action='store_false', dest='run_local',
            # TRANSLATORS: please keep the word 'local' untranslated.
            # It designates special type of jobs, not their location.
            help=_('do not run local jobs'))
        group = parser.add_argument_group("reports")
        group.add_argument(
            '-s', '--print-stats', action='store_true',
            help=_("print general job statistics"))
        group.add_argument(
            "-d", "--print-dependency-report", action='store_true',
            help=_("print dependency report"))
        group.add_argument(
            "-t", "--print-interactivity-report", action='store_true',
            help=_("print interactivity report"))
        group.add_argument(
            "-e", "--print-estimated-duration-report", action='store_true',
            help=_("print estimated duration report"))
        group.add_argument(
            "-v", "--print-validation-report", action='store_true',
            help=_("print validation report"))
        group.add_argument(
            "-r", "--print-requirement-report", action='store_true',
            help=_("print requirement report"))
        group.add_argument(
            "-E", "--only-errors", action='store_true', default=False,
            help=_(
                "when coupled with -v, only problematic jobs will be listed"))
        group.add_argument(
            "-S", "--print-desired-job-list", action='store_true',
            help=_("print desired job list"))
        group.add_argument(
            "-R", "--print-run-list", action='store_true',
            help=_("print run list"))
        parser.set_defaults(command=self)
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
