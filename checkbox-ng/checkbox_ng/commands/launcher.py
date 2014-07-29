# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
:mod:`checkbox_ng.commands.launcher` -- `checkbox launcher` command
===================================================================
"""

from gettext import gettext as _
import logging

from checkbox_ng.commands import CheckboxCommand
from checkbox_ng.commands.newcli import CliInvocation2
from checkbox_ng.launcher import LauncherDefinition


logger = logging.getLogger("checkbox.ng.commands.launcher")


class LauncherCommand(CheckboxCommand):
    """
    run a customized testing session

    This command can be used as an interpreter for the so-called launchers.
    Those launchers are small text files that define the parameters of the test
    and can be executed directly to run a customized checkbox-ng testing
    session.
    """

    def invoked(self, ns):
        try:
            with open(ns.launcher, 'rt', encoding='UTF-8') as stream:
                first_line = stream.readline()
                if not first_line.startswith("#!"):
                    stream.seek(0)
                text = stream.read()
        except IOError as exc:
            logger.error(_("Unable to load launcher definition: %s"), exc)
            return 1
        launcher = LauncherDefinition()
        launcher.read_string(text)
        if launcher.problem_list:
            logger.error(_("Unable to start launcher because of errors:"))
            for problem in launcher.problem_list:
                logger.error("%s", str(problem))
            return 1
        else:
            ns.not_interactive = False
            ns.dry_run = False
            return CliInvocation2(self.provider_list, self.config, ns,
                                  launcher).run()

    def register_parser(self, subparsers):
        parser = self.add_subcommand(subparsers)
        self.register_arguments(parser)

    def register_arguments(self, parser):
        parser.add_argument(
            "launcher", metavar=_("LAUNCHER"),
            help=_("launcher definition file to use"))
        parser.set_defaults(command=self)
