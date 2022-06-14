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


def main():
    import argparse
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
    deprecated_commands = {
        'slave': 'service',
        'master': 'remote',
    }

    known_cmds = list(commands.keys())
    known_cmds += list(deprecated_commands.keys())
    known_cmds += ['-h', '--help']
    if not (set(known_cmds) & set(sys.argv[1:])):
        sys.argv.insert(1, 'launcher')

    for i, arg in enumerate(sys.argv):
        if arg in deprecated_commands:
            sys.argv[i] = deprecated_commands[arg]
            print()
            print('WARNING: "{}" deprecated'.format(arg), end='')
            print(' please use "{}" instead.'.format(
                deprecated_commands[arg]), end='\n\n')

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
    top_parser.add_argument('subcommand', help=_("subcommand to run"),
                            choices=commands.keys())
    # parse all the cli invocation until a subcommand is found
    # subcommand doesn't start with a '-'
    subcmd_index = 1
    for i, arg in enumerate(sys.argv[1:]):
        if not arg.startswith('-'):
            subcmd_index = i + 1
            break
    args = top_parser.parse_args(sys.argv[1:subcmd_index + 1])
    subcmd_parser = argparse.ArgumentParser()
    subcmd = commands[args.subcommand]()
    subcmd.register_arguments(subcmd_parser)
    sub_args = subcmd_parser.parse_args(sys.argv[subcmd_index + 1:])
    sa = SessionAssistant(
        "com.canonical:checkbox-cli",
        "0.99",
        "0.99",
        ["restartable"],
    )
    ctx = Context(sub_args, sa)
    try:
        socket.getaddrinfo('localhost', 443)  # 443 for HTTPS
    except Exception:
        pass
    if '--clear-cache' in sys.argv:
        ResourceJobCache().clear()
    if '--clear-old-sessions' in sys.argv:
        old_sessions = [s[0] for s in sa.get_old_sessions()]
        sa.delete_sessions(old_sessions)
    if args.verbose:
        logging_level = logging.INFO
        logging.basicConfig(level=logging_level)
    if args.debug:
        logging_level = logging.DEBUG
        logging.basicConfig(level=logging_level)
    subcmd.invoked(ctx)
