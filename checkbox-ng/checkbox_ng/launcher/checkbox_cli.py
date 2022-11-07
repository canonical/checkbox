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

import argparse
import gettext
import logging
import os
import subprocess
import sys

from plainbox.impl.jobcache import ResourceJobCache
from plainbox.impl.launcher import DefaultLauncherDefinition
from plainbox.impl.launcher import LauncherDefinition
from plainbox.impl.session.assistant import SessionAssistant

from checkbox_ng.config import load_configs
from checkbox_ng.launcher.subcommands import (
    Launcher, List, Run, StartProvider, Submit, ListBootstrapped,
    TestPlanExport, Show
)
from checkbox_ng.launcher.check_config import CheckConfig
from checkbox_ng.launcher.merge_reports import MergeReports
from checkbox_ng.launcher.merge_submissions import MergeSubmissions
from checkbox_ng.launcher.master import RemoteMaster
from checkbox_ng.launcher.slave import RemoteSlave


_ = gettext.gettext

_logger = logging.getLogger("checkbox-cli")


class Context:
    def __init__(self, args, sa):
        self.args = args
        self.sa = sa


class WarnDeprecated(argparse._SubParsersAction):
    replacements = {
        'slave': 'service',
        'master': 'remote',
    }
    def __call__(self, parser, namespace, values, option_string=None):
        cmd_name = values[0]
        replacement = WarnDeprecated.replacements.get(cmd_name)
        if replacement is not None:
            print()
            print('WARNING: "{}" deprecated'.format(cmd_name), end='')
            print(' please use "{}" instead.'.format(replacement), end='\n\n')
            values[0] = replacement
        return super().__call__(parser, namespace, values, option_string)

def main():
    import argcomplete
    commands = {
        'check-config': CheckConfig,
        'launcher': Launcher,
        'list': List,
        'run': Run,
        'startprovider': StartProvider,
        'submit': Submit,
        'show': Show,
        'list-bootstrapped': ListBootstrapped,
        'merge-reports': MergeReports,
        'merge-submissions': MergeSubmissions,
        'tp-export': TestPlanExport,
        'service': RemoteSlave,
        'remote': RemoteMaster,
    }

    known_cmds = list(commands.keys())
    known_cmds += list(WarnDeprecated.replacements.keys())
    known_cmds += ['-h', '--help']
    if not (set(known_cmds) & set(sys.argv[1:])):
        sys.argv.insert(1, 'launcher')

    top_parser = argparse.ArgumentParser()
    top_parser.add_argument('-v', '--verbose', action='store_true', help=_(
        'print more logging from checkbox'))
    top_parser.add_argument('--debug', action='store_true', help=_(
        'print debug messages from checkbox'))
    top_parser.add_argument('--clear-cache', action='store_true', help=_(
        'remove cached results from the system'))
    top_parser.add_argument('--clear-old-sessions', action='store_true', help=_(
        "remove previous sessions' data"))
    top_parser.add_argument('--version', action='store_true', help=_(
        "show program's version information and exit"))

    subparsers = top_parser.add_subparsers(dest="subcommand", help=_(
        "subcommand to run"), action=WarnDeprecated)
    deprecated_aliases = {v: [k] for k, v in WarnDeprecated.replacements.items()}
    for cmd_name in commands:
        aliases = deprecated_aliases.get(cmd_name) or []
        subcmd_parser = subparsers.add_parser(cmd_name, aliases=aliases)
        subcmd_class = commands[cmd_name]
        subcmd_class.register_arguments(subcmd_parser)

    # shadow the deprecated aliases: {check-config,launcher,...}
    subparsers.metavar = "{{{}}}".format(','.join(commands.keys()))

    argcomplete.autocomplete(top_parser)
    args = top_parser.parse_args()
    subcmd = commands[args.subcommand]()
    sa = SessionAssistant(
        "com.canonical:checkbox-cli",
        "0.99",
        "0.99",
        ["restartable"],
    )
    ctx = Context(args, sa)
    try:
        socket.getaddrinfo('localhost', 443)  # 443 for HTTPS
    except Exception:
        pass
    if args.clear_cache:
        ResourceJobCache().clear()
    if args.clear_old_sessions:
        old_sessions = [s[0] for s in sa.get_old_sessions()]
        sa.delete_sessions(old_sessions)
    if args.verbose:
        logging_level = logging.INFO
        logging.basicConfig(level=logging_level)
    if args.debug:
        logging_level = logging.DEBUG
        logging.basicConfig(level=logging_level)
    subcmd.invoked(ctx)
