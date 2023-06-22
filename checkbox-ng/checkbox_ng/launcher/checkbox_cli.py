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

from copy import copy

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


def get_argparser_no_exit(*args, **kwargs):
    try:
        return argparse.ArgumentParser(*args, **kwargs)
    except TypeError:
        if "exit_on_error" not in kwargs:
            raise

    class ArgumentParserNoExit(argparse.ArgumentParser):
        # this is a bodge because exit_on_error is py3.9+
        # TODO: remove this once support for py<3.9 is dropped
        def __init__(self, *args, **kwargs):
            kwargs.pop("exit_on_error", None)
            super().__init__(*args, **kwargs)

        def error(self, message):
            # this works because if argument is none
            # __str__ will print message
            raise argparse.ArgumentError(None, message)

    return ArgumentParserNoExit(*args, **kwargs)


def parse_args(parser, default_command, deprecated_commands):
    sys_argv = copy(sys.argv)
    try:
        return parser.parse_args(args=sys_argv[1:])
    except argparse.ArgumentError as e:
        error = e
    # this could be caused by:
    #   usage of default_command
    #   usage of a deprecated command
    #   a typo

    # get all deprecated command used
    deprecated_sys_argv = [arg for arg in sys_argv if arg in deprecated_commands]
    if deprecated_sys_argv:
        # -> usage of deprecated command
        dep_command = deprecated_sys_argv[0]
        new_command = deprecated_commands[dep_command]
        _logger.warning(
            "%s is deprecated. Please use %s instead!", dep_command, new_command
        )
        # replace the first deprecated command (assuming any other is a file arg)
        sys_argv[sys_argv.index(dep_command)] = new_command
    else:
        # -> usage of default_command
        # discover where the args for the default_command start
        i = len(sys_argv)
        while i > 1:
            try:
                parser.parse_args(args=sys_argv[1:i])
                break
            except argparse.ArgumentError:
                i -= 1
        # apply the default command
        sys_argv.insert(i, default_command)
    with contextlib.suppress(argparse.ArgumentError):
        return parser.parse_args(args=sys_argv[1:])
    # -> typo is some arg
    parser.print_usage()
    raise SystemExit(str(error))


def setup_and_parse_args(default_command, commands, deprecated_commands={}):
    top_parser = get_argparser_no_exit(conflict_handler="resolve", exit_on_error=False)
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

    sub_command_parsers = top_parser.add_subparsers(
        title="subcommand",
        help=_("subcommand to run"),
        dest="subcommand",
    )
    for sub_command, action_type in commands.items():
        sub_command_parser = sub_command_parsers.add_parser(sub_command)
        action_type.register_arguments(sub_command_parser)

    args = parse_args(top_parser, default_command, deprecated_commands)
    if args.subcommand is None:
        top_parser.parse_args(args=[default_command], namespace=args)

    if "launcher" in args and args.launcher is None:
        if args.launcher_file:
            args_dict = vars(args)
            # set launcher = launcher_file
            # this is done this way because you can not overwrite default
            # values in Namespaces and having overlapping (same name)
            # args makes them overwrite each other
            args_dict["launcher"] = args.launcher_file
            args = argparse.Namespace(**args_dict)
    elif "launcher" in args and args.launcher_file:
        # both args.launcher and args.launcher_file provided
        raise SystemExit(
            "Launcher provided twice, use either --launcher or the positional arg"
        )
    return args


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

    sa = SessionAssistant(
        "com.canonical:checkbox-cli",
        "0.99",
        "0.99",
        ["restartable"],
    )

    args = setup_and_parse_args(
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
