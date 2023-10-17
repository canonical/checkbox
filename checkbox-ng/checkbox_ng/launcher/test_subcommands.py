# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

import unittest
from unittest import TestCase
from unittest.mock import patch, Mock

from checkbox_ng.launcher.subcommands import Launcher


class TestLauncher(TestCase):
    @patch("checkbox_ng.launcher.subcommands.detect_restart_strategy")
    @patch("os.getenv")
    @patch("sys.argv")
    @patch("os.path.abspath")
    def test__configure_restart(
        self, abspath_mock, sys_argv_mock, mock_getenv, mock_rs
    ):
        tested_self = Mock()
        ctx_mock = Mock()
        mock_getenv.return_value = ""
        sys_argv_mock.__getitem__.return_value = "unittest"
        abspath_mock.return_value = "launcher_path"

        Launcher._configure_restart(tested_self, ctx_mock)
        (
            get_restart_cmd_f,
        ) = ctx_mock.sa.configure_application_restart.call_args[0]
        restart_cmd = get_restart_cmd_f("session_id")
        self.assertEqual(
            restart_cmd,
            ["unittest launcher launcher_path --resume session_id"],
        )

    @patch("checkbox_ng.launcher.subcommands.detect_restart_strategy")
    @patch("os.getenv")
    @patch("sys.argv")
    @patch("os.path.abspath")
    def test__configure_restart_snap(
        self, abspath_mock, sys_argv_mock, mock_getenv, mock_rs
    ):
        tested_self = Mock()
        ctx_mock = Mock()
        mock_getenv.return_value = "snap_name"
        sys_argv_mock.__getitem__.return_value = "unittest"
        abspath_mock.return_value = "launcher_path"

        Launcher._configure_restart(tested_self, ctx_mock)
        (
            get_restart_cmd_f,
        ) = ctx_mock.sa.configure_application_restart.call_args[0]
        restart_cmd = get_restart_cmd_f("session_id")
        self.assertEqual(
            restart_cmd,
            [
                "/snap/bin/snap_name.checkbox-cli launcher "
                "launcher_path --resume session_id"
            ],
        )


class TestLauncherReturnCodes(TestCase):
    def setUp(self):
        self.launcher = Launcher()
        self.launcher._maybe_resume_session = Mock(return_value=False)
        self.launcher._start_new_session = Mock()
        self.launcher._pick_jobs_to_run = Mock()
        self.launcher._export_results = Mock()
        self.ctx = Mock()
        self.ctx.args = Mock(version=False, verify=False, launcher="")
        self.ctx.sa = Mock(
            get_resumable_sessions=Mock(return_value=[]),
            get_dynamic_todo_list=Mock(return_value=[]),
        )

    def test_invoke_returns_0_on_no_fails(self):
        mock_results = {"fail": 0, "crash": 0, "pass": 1}
        self.ctx.sa.get_summary = Mock(return_value=mock_results)
        self.assertEqual(self.launcher.invoked(self.ctx), 0)

    def test_invoke_returns_1_on_fail(self):
        mock_results = {"fail": 1, "crash": 0, "pass": 1}
        self.ctx.sa.get_summary = Mock(return_value=mock_results)
        self.assertEqual(self.launcher.invoked(self.ctx), 1)

    def test_invoke_returns_1_on_crash(self):
        mock_results = {"fail": 0, "crash": 1, "pass": 1}
        self.ctx.sa.get_summary = Mock(return_value=mock_results)
        self.assertEqual(self.launcher.invoked(self.ctx), 1)

    def test_invoke_returns_0_on_no_tests(self):
        mock_results = {"fail": 0, "crash": 0, "pass": 0}
        self.ctx.sa.get_summary = Mock(return_value=mock_results)
        self.assertEqual(self.launcher.invoked(self.ctx), 0)

    def test_invoke_returns_1_on_many_diff_outcomes(self):
        mock_results = {"fail": 6, "crash": 7, "pass": 8}
        self.ctx.sa.get_summary = Mock(return_value=mock_results)
        self.assertEqual(self.launcher.invoked(self.ctx), 1)
