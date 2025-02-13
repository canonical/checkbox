#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Tests for `_common.py`

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import subprocess
import unittest
from unittest import mock

import _common


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
                _common.run_command(*args, **kwargs)
                mocked.assert_called_with(
                    args, stderr=subprocess.STDOUT, universal_newlines=True, **kwargs
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
                result = _common.run_command()
                assert expected == result
                mocked.reset_mock()

    @mock.patch("subprocess.check_output")
    def test_raises_system_exit_on_error_with_correct_code(self, mocked):
        causing_exception = subprocess.CalledProcessError(
            2, "testing", output="out", stderr="err"
        )
        mocked.side_effect = causing_exception
        with self.assertRaises(SystemExit) as caught:
            _common.run_command("testing")
        assert caught.exception.code == causing_exception.returncode

    @mock.patch("subprocess.check_output")
    def test_raises_system_exit_on_error_with_correct_cause(self, mocked):
        causing_exception = subprocess.CalledProcessError(
            2, "testing", output="out", stderr="err"
        )
        mocked.side_effect = causing_exception
        with self.assertRaises(SystemExit) as caught:
            _common.run_command("testing")
        assert caught.exception.__cause__ == causing_exception


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
                _common.create_parser_with_checks_as_commands([])
        with self.subTest("1 check"):
            _common.create_parser_with_checks_as_commands([check_1])
        with self.subTest("2 checks"):
            _common.create_parser_with_checks_as_commands([check_1, check_2])
        with self.subTest("3 checks"):
            _common.create_parser_with_checks_as_commands([check_1, check_2, check_p2])

    def test_catches_duplicate_checks(self):
        with self.assertRaises(AssertionError):
            _common.create_parser_with_checks_as_commands(
                [check_1, check_2, check_p2, check_1]
            )

    def test_creates_expected_sub_parsesr_funcs(self):
        parser = _common.create_parser_with_checks_as_commands(
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
