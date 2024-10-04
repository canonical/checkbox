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
import itertools
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
    @patch("sys.argv", ["rvs.py", "gpup"])
    def test_parse_args_success(self, logging_mock, stderr_mock):
        args = parse_args()
        self.assertIsNotNone(args)

    @patch.object(ModuleRunner, "run", lambda self, _: 0)
    @patch(
        "rvs.parse_args", return_value=MagicMock(log_level=0, modules=["gpup"])
    )
    def test_main_successful(self, logging_mock, parse_args_mock):
        ret = main()
        self.assertEqual(ret, 0)

    @patch.object(ModuleRunner, "run", lambda self, _: 1)
    @patch(
        "rvs.parse_args", return_value=MagicMock(log_level=0, modules=["gpup"])
    )
    def test_main_failure(self, logging_mock, parse_args_mock):
        ret = main()
        self.assertEqual(ret, 1)


@patch("rvs.logging")
class TestModuleRunner(TestCase):
    @patch("subprocess.run")
    def test__run(self, logging_mock, run_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("gpup")

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, module: MagicMock(
            stdout="", stderr="[RESULT] no gpu", returncode=1
        ),
    )
    def test_run_failure(self, logging_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        ret = runner.run("gst")
        self.assertEqual(ret, 1)
        self.assertEqual(logging_mock.error.call_count, 2)

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, module: MagicMock(stdout="", stderr="", returncode=1),
    )
    def test_run_failure_no_stderr(self, logging_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        ret = runner.run("gst")
        self.assertEqual(ret, 1)
        self.assertEqual(logging_mock.error.call_count, 1)

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, module: MagicMock(
            stderr="", stdout="[RESULT] info", returncode=0
        ),
    )
    def test_run_success(self, logging_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        ret = runner.run("gst")
        self.assertEqual(ret, 0)
        self.assertTrue(logging_mock.info.called)
        self.assertEqual(logging_mock.debug.call_count, 2)

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, module: MagicMock(
            stderr="[DEBUG] debug", stdout="[RESULT] info", returncode=0
        ),
    )
    def test_run_success_stderr(self, logging_mock):
        runner = ModuleRunner(RVS_BIN, Path("."))
        ret = runner.run("gst")
        self.assertEqual(ret, 0)
        self.assertTrue(logging_mock.debug.call_count, 3)


@patch("rvs.logging")
class TestPassFailModuleRunner(TestCase):
    @patch.object(
        ModuleRunner, "_run", lambda self, module: MagicMock(returncode=1)
    )
    def test__run_error(self, logging_mock):
        runner = PassFailModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("gst")
        self.assertEqual(proc.returncode, 1)

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, module: MagicMock(
            stdout="[RESULT] pass: FALSE", returncode=0
        ),
    )
    def test__run_failure(self, logging_mock):
        runner = PassFailModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("gst")
        self.assertEqual(proc.returncode, 1)

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, module: MagicMock(
            stdout="[RESULT] pass: TRUE", returncode=0
        ),
    )
    def test__run_success(self, logging_mock):
        runner = PassFailModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("gst")
        self.assertEqual(proc.returncode, 0)


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

    @patch.object(
        ModuleRunner, "_run", lambda self, _: MagicMock(returncode=1)
    )
    def test__run_error(self, logging_mock):
        runner = MemModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("mem")
        self.assertEqual(proc.returncode, 1)

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, _: MagicMock(
            stdout=TestMemModuleRunner.FAIL_OUT, returncode=0
        ),
    )
    def test__run_failure(self, logging_mock):
        runner = MemModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("mem")
        self.assertEqual(proc.returncode, 1)

    @patch.object(
        ModuleRunner,
        "_run",
        lambda self, _: MagicMock(
            stdout=TestMemModuleRunner.PASS_OUT, returncode=0
        ),
    )
    def test__run_success(self, logging_mock):
        runner = MemModuleRunner(RVS_BIN, Path("."))
        proc = runner._run("mem")
        self.assertEqual(proc.returncode, 0)
