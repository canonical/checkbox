#!/usr/bin/env python3
"""Copyright (C) 2024 Canonical Ltd.

Authors
  Pedro Avalos Jimenez <pedro.avalosjimenez@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import io
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from rvs import (
    RVS_BIN,
    MemModuleRunner,
    ModuleRunner,
    PassFailModuleRunner,
    main,
    parse_args,
    which_rvs,
)


@patch("rvs.logging")
class TestMain(TestCase):
    @patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="/bin/rvs"),
    )
    def test_which_rvs_found(self, run_mock, logging_mock):
        p = which_rvs()
        self.assertEqual(p, Path(run_mock().stdout.strip()))

    @patch("subprocess.run", side_effect=MagicMock(returncode=1))
    def test_which_rvs_fallback(self, run_mock, logging_mock):
        p = which_rvs()
        self.assertEqual(p, RVS_BIN)

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.argv", ["rvs.py", "--list-modules"])
    def test_parse_args_list_modules(self, logging_mock, stderr_mock):
        with self.assertRaises(SystemExit) as cm:
            args = parse_args()
        self.assertEqual(cm.exception.code, 0)

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.argv", ["rvs.py"])
    def test_parse_args_failure(self, logging_mock, stderr_mock):
        with self.assertRaises(SystemExit) as cm:
            args = parse_args()
        self.assertEqual(cm.exception.code, 2)

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.argv", ["rvs.py", "invalid_module"])
    def test_parse_args_invalid_module(self, logging_mock, stderr_mock):
        with self.assertRaises(SystemExit) as cm:
            args = parse_args()
        self.assertEqual(cm.exception.code, 2)

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.argv", ["rvs.py", "gpup"])
    def test_parse_args_success(self, stderr_mock, logging_mock):
        args = parse_args()
        self.assertIsNotNone(args)

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.argv", ["rvs.py", "gpup", "-c", "./config.conf"])
    def test_parse_args_success_config(self, stderr_mock, logging_mock):
        args = parse_args()
        self.assertIsNotNone(args)

    @patch.object(ModuleRunner, "run")
    @patch(
        "rvs.parse_args", return_value=MagicMock(log_level=0, module="gpup")
    )
    def test_main_successful(self, parse_args_mock, run_mock, logging_mock):
        try:
            main()
        except SystemExit:
            self.fail("main raised SystemExit!")

    @patch.object(ModuleRunner, "run", side_effect=SystemExit(1))
    @patch(
        "rvs.parse_args", return_value=MagicMock(log_level=0, module="gpup")
    )
    def test_main_failure(self, parse_args_mock, run_mock, logging_mock):
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)


@patch("rvs.logging")
class TestModuleRunner(TestCase):
    @patch("subprocess.run")
    def test__run(self, logging_mock, run_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("gpup")

    def test__validate_output_success(self, logging_mock):
        proc = MagicMock(returncode=0)
        runner = ModuleRunner(RVS_BIN, Path("."))
        try:
            runner._validate_output(proc, "gpup")
        except SystemExit:
            self.fail("ModuleRunner._validate_output raised SystemExit!")

    def test__validate_output_failure(self, logging_mock):
        proc = MagicMock(returncode=1, stderr="[DEBUG] debug")
        runner = ModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner._validate_output(proc, "gpup")
        self.assertEqual(cm.exception.code, 1)

    def test__validate_output_failure_stderr(self, logging_mock):
        proc = MagicMock(returncode=1, stderr="")
        runner = ModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner._validate_output(proc, "gpup")
        self.assertEqual(cm.exception.code, 1)

    @patch.object(ModuleRunner, "_validate_output", side_effect=SystemExit(1))
    @patch.object(ModuleRunner, "_run", return_value=MagicMock(stdout=""))
    def test_run_failure(self, _run_mock, _validate_output_mock, logging_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner.run("gpup")
        self.assertEqual(cm.exception.code, 1)

    @patch.object(ModuleRunner, "_validate_output", side_effect=SystemExit(1))
    @patch.object(
        ModuleRunner, "_run", return_value=MagicMock(stdout="no gpu")
    )
    def test_run_failure_stdout(
        self, _run_mock, _validate_output_mock, logging_mock
    ):
        runner = ModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner.run("gpup")
        self.assertEqual(cm.exception.code, 1)

    @patch.object(ModuleRunner, "_validate_output")
    @patch.object(
        ModuleRunner,
        "_run",
        return_value=MagicMock(stdout="[RESULT] info", stderr=""),
    )
    def test_run_success(self, _run_mock, _validate_output_mock, logging_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        try:
            runner.run("gpup")
        except SystemExit:
            self.fail("ModuleRunner.run raised SystemExit!")
        self.assertTrue(logging_mock.debug.call_count, 2)

    @patch.object(ModuleRunner, "_validate_output")
    @patch.object(
        ModuleRunner,
        "_run",
        return_value=MagicMock(stderr="[DEBUG] debug", stdout="[RESULT] info"),
    )
    def test_run_success_stderr(
        self, _run_mock, _validate_output_mock, logging_mock
    ):
        runner = ModuleRunner(RVS_BIN, Path("."))
        try:
            runner.run("gpup")
        except SystemExit:
            self.fail("ModuleRunner.run raised SystemExit!")
        self.assertTrue(logging_mock.debug.call_count, 3)


@patch("rvs.logging")
class TestPassFailModuleRunner(TestCase):
    PASS_OUT = "[RESULT] pass: TRUE"
    FAIL_OUT = "[RESULT] pass: FALSE"

    @patch.object(ModuleRunner, "_validate_output")
    def test__validate_output_success(
        self, _validate_output_mock, logging_mock
    ):
        proc = MagicMock(stderr="", stdout=self.PASS_OUT)
        runner = PassFailModuleRunner(RVS_BIN, Path("."))
        try:
            runner._validate_output(proc, "gst")
        except SystemExit:
            self.fail("PassFailModuleRunner._validate_output raised SystemExit!")

    @patch.object(ModuleRunner, "_validate_output")
    def test__validate_output_failure(
        self, _validate_output_mock, logging_mock
    ):
        proc = MagicMock(stderr="", stdout=self.FAIL_OUT)
        runner = PassFailModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner._validate_output(proc, "gpup")
        self.assertEqual(cm.exception.code, 1)

    @patch.object(ModuleRunner, "_validate_output")
    def test__validate_output_failure_stderr(
        self, _validate_output_mock, logging_mock
    ):
        proc = MagicMock(stderr="[DEBUG] info", stdout=self.FAIL_OUT)
        runner = PassFailModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner._validate_output(proc, "gpup")
        self.assertEqual(cm.exception.code, 1)


@patch("rvs.logging")
class TestMemModuleRunner(TestCase):
    FAIL_OUT = """
    [RESULT] mem Test 1 : PASS
    [RESULT] mem Test 2 : FAIL
    [RESULT] mem Test 3 : PASS
    [RESULT] mem Test 4 : PASS
    [RESULT] mem Test 5 : PASS
    [RESULT] mem Test 6 : PASS
    [RESULT] mem Test 7 : PASS
    [RESULT] mem Test 8 : PASS
    [RESULT] mem Test 9 : PASS
    [RESULT] mem Test 10 : PASS
    [RESULT] mem Test 11 : PASS
    """

    PASS_OUT = """
    [RESULT] mem Test 1 : PASS
    [RESULT] mem Test 2 : PASS
    [RESULT] mem Test 3 : PASS
    [RESULT] mem Test 4 : PASS
    [RESULT] mem Test 5 : PASS
    [RESULT] mem Test 6 : PASS
    [RESULT] mem Test 7 : PASS
    [RESULT] mem Test 8 : PASS
    [RESULT] mem Test 9 : PASS
    [RESULT] mem Test 10 : PASS
    [RESULT] mem Test 11 : PASS
    """

    @patch.object(ModuleRunner, "_validate_output")
    def test__validate_output_success(
        self, _validate_output_mock, logging_mock
    ):
        proc = MagicMock(stderr="", stdout=self.PASS_OUT)
        runner = MemModuleRunner(RVS_BIN, Path("."))
        try:
            runner._validate_output(proc, "mem")
        except SystemExit:
            self.fail("MemModuleRunner._validate_output raised SystemExit!")

    @patch.object(ModuleRunner, "_validate_output")
    def test__validate_output_failure(
        self, _validate_output_mock, logging_mock
    ):
        proc = MagicMock(stderr="", stdout=self.FAIL_OUT)
        runner = MemModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner._validate_output(proc, "mem")
        self.assertEqual(cm.exception.code, 1)

    @patch.object(ModuleRunner, "_validate_output")
    def test__validate_output_failure_stderr(
        self, _validate_output_mock, logging_mock
    ):
        proc = MagicMock(stderr="[DEBUG] debug", stdout=self.FAIL_OUT)
        runner = MemModuleRunner(RVS_BIN, Path("."))
        with self.assertRaises(SystemExit) as cm:
            runner._validate_output(proc, "mem")
        self.assertEqual(cm.exception.code, 1)
