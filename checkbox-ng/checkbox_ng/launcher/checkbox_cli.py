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
import sys

import checkbox_ng

from plainbox.impl.jobcache import ResourceJobCache
from plainbox.impl.session.assistant import SessionAssistant

from checkbox_ng.utils import set_all_loggers_level
from checkbox_ng.launcher.subcommands import (
    Launcher,
    List,
    Run,
    StartProvider,
    Submit,
    ListBootstrapped,
    Expand,
    TestPlanExport,
    Show,
)
from checkbox_ng.launcher.check_config import CheckConfig
from checkbox_ng.launcher.merge_reports import MergeReports
from checkbox_ng.launcher.merge_submissions import MergeSubmissions
from checkbox_ng.launcher.controller import RemoteController
from checkbox_ng.launcher.agent import RemoteAgent


_ = gettext.gettext

_logger = logging.getLogger("checkbox-cli")


class Context:
    def __init__(self, args, sa):
        self.args = args
        self.sa = sa

    def reset_sa(self):
        self.sa = SessionAssistant()


def handle_top_parser(args, ctx):
    """
    The top level parser may not contain all args as "launcher" is inserted
    to get a default command. Lets handle the args as stings here and unify the
    args (from the top level parser) and ctx.args (from the sub parser)
    """
    if "--debug" in sys.argv:
        logging_level = logging.DEBUG
        logging.basicConfig(level=logging_level)
        set_all_loggers_level(logging.DEBUG)
        ctx.args.debug = True
    elif "--verbose" in sys.argv or "-v" in sys.argv:
        logging_level = logging.INFO
        logging.basicConfig(level=logging_level)
        set_all_loggers_level(logging.INFO)
        ctx.args.verbose = True
    if "--clear-cache" in sys.argv:
        ResourceJobCache().clear()
        ctx.args.clear_cache = True
    if "--clear-old-sessions" in sys.argv:
        old_sessions = [s[0] for s in ctx.sa.get_old_sessions()]
        ctx.sa.delete_sessions(old_sessions)
        ctx.args.clear_old_sessions = True
    if "--version" in sys.argv:
        print(checkbox_ng.__version__)
        raise SystemExit(0)
    return ctx


def main():
    import argparse

    commands = {
        "check-config": CheckConfig,
        "launcher": Launcher,
        "list": List,
        "run": Run,
        "startprovider": StartProvider,
        "submit": Submit,
        "show": Show,
        "list-bootstrapped": ListBootstrapped,
        "expand": Expand,
        "merge-reports": MergeReports,
        "merge-submissions": MergeSubmissions,
        "tp-export": TestPlanExport,
        "run-agent": RemoteAgent,
        "control": RemoteController,
    }
    deprecated_commands = {
        "slave": "run-agent",
        "service": "run-agent",
        "master": "control",
        "remote": "control",
    }

    known_cmds = list(commands.keys())
    known_cmds += list(deprecated_commands.keys())
    known_cmds += ["-h", "--help"]
    if not (set(known_cmds) & set(sys.argv[1:])):
        sys.argv.insert(1, "launcher")

    for i, arg in enumerate(sys.argv):
        if arg in deprecated_commands:
            sys.argv[i] = deprecated_commands[arg]
            logging.warning(
                # "%s is deprecated. Please use %s instead",
                "%s is deprecated and will be removed in the next major release of Checkbox. Please use %s instead",
                arg,
                deprecated_commands[arg],
            )

    top_parser = argparse.ArgumentParser()
    # You must handle these args in the function above, see docstring
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
        "subcommand", help=_("subcommand to run"), choices=commands.keys()
    )
    # parse all the cli invocation until a subcommand is found
    # subcommand doesn't start with a '-'
    subcmd_index = 1
    for i, arg in enumerate(sys.argv[1:]):
        if not arg.startswith("-"):
            subcmd_index = i + 1
            break
    args = top_parser.parse_args(sys.argv[1 : subcmd_index + 1])
    subcmd_parser = argparse.ArgumentParser()
    subcmd = commands[args.subcommand]()
    subcmd.register_arguments(subcmd_parser)
    sub_args = subcmd_parser.parse_args(sys.argv[subcmd_index + 1 :])
    sa = SessionAssistant()
    ctx = Context(sub_args, sa)
    ctx = handle_top_parser(args, ctx)
    return subcmd.invoked(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
