#!/usr/bin/env python3
# Copyright 2018-2022 Canonical Ltd.
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
