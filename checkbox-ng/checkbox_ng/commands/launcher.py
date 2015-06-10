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

from argparse import SUPPRESS
from gettext import gettext as _
import itertools
import logging
import os

from checkbox_ng.commands import CheckboxCommand
from checkbox_ng.commands.newcli import CliInvocation2
from checkbox_ng.commands.submit import SubmitCommand
from checkbox_ng.config import CheckBoxConfig
from checkbox_ng.launcher import LauncherDefinition

from plainbox.impl.commands.cmd_checkbox import CheckBoxCommandMixIn

logger = logging.getLogger("checkbox.ng.commands.launcher")


class LauncherCommand(CheckboxCommand, CheckBoxCommandMixIn, SubmitCommand):
    """
    run a customized testing session

    This command can be used as an interpreter for the so-called launchers.
    Those launchers are small text files that define the parameters of the test
    and can be executed directly to run a customized checkbox-ng testing
    session.
    """

    def __init__(self, provider_loader, config_loader):
        self._provider_loader = provider_loader
        self.config = config_loader()

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
        # Override the default CheckBox configuration with the one provided
        # by the launcher
        self.config.Meta.filename_list = list(
            itertools.chain(
                *zip(
                    itertools.islice(
                        CheckBoxConfig.Meta.filename_list, 0, None, 2),
                    itertools.islice(
                        CheckBoxConfig.Meta.filename_list, 1, None, 2),
                    ('/etc/xdg/{}'.format(launcher.config_filename),
                        os.path.expanduser(
                            '~/.config/{}'.format(launcher.config_filename)))))
            )
        self.config.read(self.config.Meta.filename_list)
        ns.dry_run = False
        ns.dont_suppress_output = launcher.dont_suppress_output
        return CliInvocation2(
            self.provider_loader, lambda: self.config, ns, launcher
        ).run()

    def register_parser(self, subparsers):
        parser = self.add_subcommand(subparsers)
        self.register_arguments(parser)

    def register_arguments(self, parser):
        parser.add_argument(
            '--no-color', dest='color', action='store_false', help=SUPPRESS)
        parser.set_defaults(color=None)
        parser.add_argument(
            "launcher", metavar=_("LAUNCHER"),
            help=_("launcher definition file to use"))
        parser.set_defaults(command=self)
        parser.conflict_handler = 'resolve'
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
        group = parser.add_argument_group(title=_("user interface options"))
        group.add_argument(
            '--non-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        # Call register_optional_arguments from SubmitCommand
        self.register_optional_arguments(parser)
