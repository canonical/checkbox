#!/usr/bin/env python3
# Copyright 2018-2022 Canonical Ltd.
# All rights reserved.
#
"""Common utilities for the checkbox-provider-dss

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import argparse
import inspect
import subprocess
import typing as t


def create_parser_with_checks_as_commands(
    checks: t.List[t.Callable], **kwargs
) -> argparse.ArgumentParser:
    assert len(checks) > 0, "must provide at least one check"
    assert len(checks) == len(set(checks)), "duplicate checks are not allowed"

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
        result = result.strip()
        return result
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e
