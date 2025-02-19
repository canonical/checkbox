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
"""Tests for `common.py`"""

import subprocess
import unittest
from unittest import mock

import common

# pragma: no cover


class TestRunCommand(unittest.TestCase):
    @mock.patch("subprocess.check_output")
    def test_calls_subprocess(self, mocked):
        for i, (args, kwargs) in enumerate(
            [
                [("ls", "-lah"), {"timeout": 30}],
                [("ls", "-lh"), {}],
            ]
        ):
            with self.subTest(i=i):
                assert isinstance(kwargs, dict)
                common.run_command(*args, **kwargs)
                mocked.assert_called_with(
                    args,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    **kwargs,
                )
                mocked.reset_mock()

    @mock.patch("subprocess.check_output")
    def test_returns_stripped_output_from_subprocess(self, mocked):
        for i, (value, expected) in enumerate(
            [
                ("something", "something"),
                (" with spaces   ", "with spaces"),
                ("\nmulti \nline ", "multi \nline"),
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = value
                result = common.run_command()
                assert expected == result
                mocked.reset_mock()

    @mock.patch("subprocess.check_output")
    def test_raises_subprocess_error(self, mocked):
        exception = subprocess.CalledProcessError(
            2, "testing", output="out", stderr="err"
        )
        mocked.side_effect = exception
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            common.run_command("testing")
        assert caught.exception == exception


def check_1():
    """check 1"""
    return 1


def check_2():
    """check 2"""
    return 2


def check_p2(n: int):
    """check p2"""
    return n**2


class TestCreateParserWithChecks(unittest.TestCase):
    def test_accepts_at_least_one_check(self):
        with self.subTest("no checks"):
            with self.assertRaises(AssertionError):
                common.create_parser_with_checks_as_commands([])
        with self.subTest("1 check"):
            common.create_parser_with_checks_as_commands([check_1])
        with self.subTest("2 checks"):
            common.create_parser_with_checks_as_commands([check_1, check_2])
        with self.subTest("3 checks"):
            common.create_parser_with_checks_as_commands(
                [
                    check_1,
                    check_2,
                    check_p2,
                ]
            )

    def test_catches_duplicate_checks(self):
        with self.assertRaises(AssertionError):
            common.create_parser_with_checks_as_commands(
                [check_1, check_2, check_p2, check_1]
            )

    def test_creates_expected_sub_parsesr_funcs(self):
        parser = common.create_parser_with_checks_as_commands(
            [check_1, check_2, check_p2]
        )
        for check, args in [
            (check_1, ["check_1"]),
            (check_2, ["check_2"]),
            (check_p2, ["check_p2", "2"]),
        ]:
            with self.subTest(check):
                parsed = parser.parse_args(args)
                assert parsed.func == check

    # XXX:@motjuste: argparse provides very limited introspecting for sub-parsers?
    #   Otherwise, tests should be added about setting appropriate help, type, and
    #   description for the sub-parsers
