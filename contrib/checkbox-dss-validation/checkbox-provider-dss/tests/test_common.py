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

import unittest

import common


def check_1():
    """check 1"""
    return 1


def check_2():
    """check 2"""
    return 2


def check_p2(n: int):
    """check p2"""
    assert isinstance(n, int)
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
            with self.subTest(check.__name__):
                parsed = parser.parse_args(args)
                parsed_dict = dict(parsed.__dict__)
                func = parsed_dict.pop("func")
                self.assertEqual(func, check)

    def test_checks_without_args_are_called(self):
        parser = common.create_parser_with_checks_as_commands(
            [check_1, check_2]
        )
        for check, args, expected in [
            (check_1, ["check_1"], 1),
            (check_2, ["check_2"], 2),
        ]:
            with self.subTest(check.__name__):
                parsed = parser.parse_args(args)
                parsed_dict = dict(parsed.__dict__)
                func = parsed_dict.pop("func")
                self.assertEqual(func(**parsed_dict), expected)

    def test_exits_with_code_2_for_missing_args(self):
        parser = common.create_parser_with_checks_as_commands([check_p2])
        with self.assertRaises(SystemExit) as caught:
            parser.parse_args(["check_p2"])  # no required arg
        self.assertEqual(caught.exception.code, 2)

    def test_parses_required_arg(self):
        parser = common.create_parser_with_checks_as_commands([check_p2])
        parsed = parser.parse_args(["check_p2", "2"])
        parsed_dict = dict(parsed.__dict__)
        func = parsed_dict.pop("func")
        self.assertEqual(func(**parsed_dict), 2**2)

    # XXX:@motjuste: argparse provides very limited introspecting for sub-parsers?
    #   Otherwise, tests should be added about setting appropriate help, type, and
    #   description for the sub-parsers
