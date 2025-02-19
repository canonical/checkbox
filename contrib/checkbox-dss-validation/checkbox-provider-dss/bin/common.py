#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
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
#
"""Common utilities for the checkbox-provider-dss"""

import argparse
import inspect
import subprocess
import typing as t


def create_parser_with_checks_as_commands(
    checks: t.List[t.Callable], **kwargs
) -> argparse.ArgumentParser:
    if len(checks) <= 0:
        raise AssertionError("must provide at least one check")

    if len(checks) != len(set(checks)):
        # NOTE:@motjuste: Python 3.10 does not de-duplicate sub parser commands
        raise AssertionError("duplicate checks are not allowed")

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, **kwargs
    )
    sub_parsers = parser.add_subparsers(required=True)

    for check in checks:
        command_parser = sub_parsers.add_parser(
            check.__name__, description=check.__doc__, help=check.__doc__
        )
        command_parser.set_defaults(func=check)
        for name, param in inspect.signature(check).parameters.items():
            assert param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
            assert param.annotation is not bool
            assert param.default is inspect._empty

            command_parser.add_argument(name, type=param.annotation)

    return parser


def run_command(*command: str, **kwargs) -> str:
    """Run a shell command and return its output"""
    try:
        result = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,  # We capture stdout and stderr in stdout
            universal_newlines=True,
            **kwargs,
        )
        print(result)
        result = result.strip()
        return result
    except subprocess.CalledProcessError as err:
        print(err.stdout)
        print(err.stderr)
        raise
