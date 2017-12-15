# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
Checkbox Launcher Interpreter Application
"""

import gettext
import logging
import os
import subprocess
import sys

from guacamole.core import Ingredient
from guacamole.ingredients import ansi
from guacamole.ingredients import argparse
from guacamole.ingredients import cmdtree
from guacamole.recipes.cmd import CommandRecipe

from plainbox.impl.ingredients import CanonicalCrashIngredient
from plainbox.impl.ingredients import CanonicalCommand
from plainbox.impl.ingredients import RenderingContextIngredient
from plainbox.impl.ingredients import SessionAssistantIngredient
from plainbox.impl.launcher import DefaultLauncherDefinition
from plainbox.impl.launcher import LauncherDefinition

from checkbox_ng.launcher.subcommands import (
    CheckConfig, Launcher, List, Run, StartProvider, Submit, ListBootstrapped
)
from checkbox_ng.launcher.remote import RemoteService, RemoteControl


_ = gettext.gettext

_logger = logging.getLogger("checkbox-cli")


class DisplayIngredient(Ingredient):

    """Ingredient that adds a Textland display to guacamole."""

    def late_init(self, context):
        """Add a DisplayIngredient as ``display`` to the guacamole context."""
        context.display = get_display()


class WarmupCommandsIngredient(Ingredient):
    """Ingredient that runs given commands at startup."""
    def late_init(self, context):
        # https://bugs.launchpad.net/checkbox-ng/+bug/1423949
        # MAAS-deployed server images need "tput reset" to keep ugliness
        # from happening....
        subprocess.check_call(['tput', 'reset'])


class LauncherIngredient(Ingredient):
    """Ingredient that adds Checkbox Launcher support to guacamole."""
    def late_init(self, context):
        if context.args.command1.get_cmd_name() != 'launcher':
            context.cmd_toplevel.launcher = DefaultLauncherDefinition()
            return
        if not context.args.launcher:
            # launcher not supplied from cli - using the default one
            launcher = DefaultLauncherDefinition()
            configs = [
                '/etc/xdg/{}'.format(launcher.config_filename),
                os.path.expanduser(
                    '~/.config/{}'.format(launcher.config_filename))]
        else:
            configs = [context.args.launcher]
            try:
                with open(context.args.launcher,
                          'rt', encoding='UTF-8') as stream:
                    first_line = stream.readline()
                    if not first_line.startswith("#!"):
                        stream.seek(0)
                    text = stream.read()
            except IOError as exc:
                _logger.error(_("Unable to load launcher definition: %s"), exc)
                raise SystemExit(1)
            generic_launcher = LauncherDefinition()
            generic_launcher.read_string(text)
            config_filename = os.path.expandvars(
                generic_launcher.config_filename)
            # if wrapper specifies just the basename
            if not os.path.split(config_filename)[0]:
                if "SNAP_DATA" in os.environ:
                    configs = [context.args.launcher]
                    configs.append(os.path.join(
                        os.path.expandvars('$SNAP_DATA'), config_filename))
                else:
                    configs += [
                        '/etc/xdg/{}'.format(config_filename),
                        os.path.expanduser('~/.config/{}'.format(
                            config_filename))]
            # if wrapper specifies an absolute file
            else:
                configs.append(config_filename)
            launcher = generic_launcher.get_concrete_launcher()
        launcher.read(configs)
        if launcher.problem_list:
            _logger.error(_("Unable to start launcher because of errors:"))
            for problem in launcher.problem_list:
                _logger.error("%s", str(problem))
            raise SystemExit(1)
        context.cmd_toplevel.launcher = launcher


class CheckboxCommandRecipe(CommandRecipe):

    """A recipe for using Checkbox-enhanced commands."""

    def get_ingredients(self):
        """Get a list of ingredients for guacamole."""
        return [
            cmdtree.CommandTreeBuilder(self.command),
            cmdtree.CommandTreeDispatcher(),
            argparse.ParserIngredient(),
            CanonicalCrashIngredient(),
            ansi.ANSIIngredient(),
            LauncherIngredient(),
            SessionAssistantIngredient(),
            RenderingContextIngredient(),
        ]


class CheckboxCommand(CanonicalCommand):

    """
    A command with Checkbox-enhanced ingredients.

    If no command is given, launcher command is assumed.
    See checkbox-cli launcher -h for more information
    """

    bug_report_url = "https://bugs.launchpad.net/checkbox-ng/+filebug"

    sub_commands = (
        ('check-config', CheckConfig),
        ('launcher', Launcher),
        ('list', List),
        ('run', Run),
        ('startprovider', StartProvider),
        ('submit', Submit),
        ('list-bootstrapped', ListBootstrapped),
        ('remote-service', RemoteService),
        ('remote-control', RemoteControl),
    )

    def register_arguments(self, parser):
        parser.add_argument('-v', '--verbose', action='store_true', help=_(
            'print more logging from checkbox'))
        parser.add_argument('--debug', action='store_true', help=_(
            'print debug messages from checkbox'))

    def invoked(self, ctx):
        if ctx.args.verbose:
            logging_level = logging.INFO
            logging.basicConfig(level=logging_level)
        if ctx.args.debug:
            logging_level = logging.DEBUG
            logging.basicConfig(level=logging_level)

    def main(self, argv=None, exit=True):
        """
        Shortcut for running a command.

        See :meth:`guacamole.recipes.Recipe.main()` for details.
        """
        return CheckboxCommandRecipe(self).main(argv, exit)


def main():
    # the next block preserves checkbox-cli universal invocation, i.e.:
    # $ checkbox-cli             -> runs default settings
    # $ checkbox-cli my-launcher -> runs checkbox-cli with `my-launcher` as
    #                               launcher
    # $ checkbox-cli launcher my-launcher ->  same as ^
    # to achieve that the following code 'injects launcher subcommand to argv
    known_cmds = [x[0] for x in CheckboxCommand.sub_commands]
    known_cmds += ['-h', '--help']
    if not (set(known_cmds) & set(sys.argv[1:])):
        sys.argv.insert(1, 'launcher')
    CheckboxCommand().main()
