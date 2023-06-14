# This file is part of Checkbox.
#
# Copyright 2016-2023 Canonical Ltd.
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
import argparse
import os
import subprocess
import sys
import itertools
import contextlib
import functools

from plainbox.impl.jobcache import ResourceJobCache
from plainbox.impl.session.assistant import SessionAssistant

from checkbox_ng.config import load_configs
from checkbox_ng.launcher.subcommands import (
    Launcher,
    List,
    Run,
    StartProvider,
    Submit,
    ListBootstrapped,
    TestPlanExport,
    Show,
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


def parse_args(default_command, commands, deprecated_commands={}):
    top_parser = argparse.ArgumentParser()
    top_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=_("print more logging from checkbox"),
    )
    top_parser.add_argument(
        "--debug",
        action="store_true",
        help=_("print debug messages from checkbox"),
    )
    top_parser.add_argument(
        "--clear-cache",
        action="store_true",
        help=_("remove cached results from the system"),
    )
    top_parser.add_argument(
        "--clear-old-sessions",
        action="store_true",
        help=_("remove previous sessions' data"),
    )
    top_parser.add_argument(
        "--version",
        action="store_true",
        help=_("show program's version information and exit"),
    )
    top_parser.add_argument(
        "--launcher",
        nargs="?",
        dest="launcher_file",
        help=_("launcher definition file to use"),
    )
    # This is used to remove deprecated commands from the usage
    metavar_str = "{{{}}}".format(
        ",".join(
            sub_command
            for sub_command in commands
            if sub_command not in deprecated_commands
        )
    )
    sub_command_parsers = top_parser.add_subparsers(
        title="subcommand",
        help=_("subcommand to run"),
        dest="subcommand",
        metavar=metavar_str,
    )
    for sub_command, action_type in commands.items():
        sub_command_parser = sub_command_parsers.add_parser(sub_command)
        action_type.register_arguments(sub_command_parser)

    args, remaning = top_parser.parse_known_args()
    if args.subcommand is None:
        remaning.insert(0, default_command)
        args = top_parser.parse_args(remaning, namespace=args)
    if "launcher" in args and args.launcher is None:
        if args.launcher_file:
            args_dict = vars(args)
            # set launcher = launcher_file
            # this is done this way because you can not overwrite default
            # values in Namespaces and having overlapping (same name)
            # args makes them overwrite each other
            args_dict["launcher"] = args.launcher_file
            args = argparse.Namespace(**args_dict)
    return args


def deprecated_command(old_name, new_name, obj):
    class _wrap(obj):
        def __init__(self, *args, **kwargs):
            _logger.warning(
                "%s is deprecated. Please use %s instead!", old_name, new_name
            )
            super().__init__(*args, **kwargs)

    return _wrap


def main():
    commands = {
        "check-config": CheckConfig,
        "launcher": Launcher,
        "list": List,
        "run": Run,
        "startprovider": StartProvider,
        "submit": Submit,
        "show": Show,
        "list-bootstrapped": ListBootstrapped,
        "merge-reports": MergeReports,
        "merge-submissions": MergeSubmissions,
        "tp-export": TestPlanExport,
        "service": RemoteSlave,
        "remote": RemoteMaster,
    }
    deprecated_commands = {
        "slave": "service",
        "master": "remote",
    }

    for deprecated_name, new_name in deprecated_commands.items():
        commands[deprecated_name] = deprecated_command(
            deprecated_name, new_name, commands[new_name]
        )

    sa = SessionAssistant(
        "com.canonical:checkbox-cli",
        "0.99",
        "0.99",
        ["restartable"],
    )

    args = parse_args(
        default_command="launcher",
        commands=commands,
        deprecated_commands=deprecated_commands,
    )

    ctx = Context(args, sa)
    try:
        socket.getaddrinfo("localhost", 443)  # 443 for HTTPS
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
    subcmd = commands[args.subcommand]()
    subcmd.invoked(ctx)
