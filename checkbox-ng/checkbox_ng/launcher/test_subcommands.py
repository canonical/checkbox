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

from unittest.mock import patch, Mock, MagicMock, call
from io import StringIO
from checkbox_ng.launcher.subcommands import (
    Launcher,
    ResumeInstead,
    IJobResult,
)
from unittest.mock import patch, Mock, MagicMock


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

    @patch("checkbox_ng.launcher.subcommands.ResumeMenu")
    def test__maybe_manually_resume_session_delete(self, resume_menu_mock):
        self_mock = MagicMock()
        resume_menu_mock().run().action = "delete"

        # delete something, the check should see that the entries list is
        # empty and return false as there is nothing to maybe resume
        self.assertFalse(
            Launcher._maybe_manually_resume_session(self_mock, [])
        )

    @patch("checkbox_ng.launcher.subcommands.ResumeMenu")
    def test__maybe_manually_resume_session(self, resume_menu_mock):
        self_mock = MagicMock()
        resume_menu_mock().run().session_id = "nonempty"

        # the user has selected something from the list, we notice
        self.assertTrue(Launcher._maybe_manually_resume_session(self_mock, []))
        # and we try to resume the session
        self.assertTrue(self_mock._resume_session.called)

    @patch("checkbox_ng.launcher.subcommands.MemoryJobResult")
    @patch("checkbox_ng.launcher.subcommands.newline_join", new=MagicMock())
    def test__resume_session_pass(self, memory_job_result_mock):
        self_mock = MagicMock()
        session_metadata_mock = self_mock.ctx.sa.resume_session.return_value
        session_metadata_mock.flags = ["testplanless"]

        resume_params_mock = MagicMock()
        resume_params_mock.action = "pass"

        Launcher._resume_session(self_mock, resume_params_mock)

        args, _ = memory_job_result_mock.call_args_list[-1]
        result_dict, *_ = args
        self.assertEqual(result_dict["outcome"], IJobResult.OUTCOME_PASS)

    @patch("checkbox_ng.launcher.subcommands.MemoryJobResult")
    @patch("checkbox_ng.launcher.subcommands.newline_join", new=MagicMock())
    def test__resume_session_fail_cert_blocker(self, memory_job_result_mock):
        self_mock = MagicMock()
        self_mock.ctx.sa.get_job_state.return_value.effective_certification_status = (
            "blocker"
        )

        session_metadata_mock = self_mock.ctx.sa.resume_session.return_value
        session_metadata_mock.flags = ["testplanless"]

        resume_params_mock = MagicMock()
        resume_params_mock.action = "fail"

        Launcher._resume_session(self_mock, resume_params_mock)

        args, _ = memory_job_result_mock.call_args_list[-1]
        result_dict, *_ = args
        # failing cert blockers with no comment needed dont get a outcome
        self.assertNotIn("outcome", result_dict)

    @patch("checkbox_ng.launcher.subcommands.MemoryJobResult")
    @patch("checkbox_ng.launcher.subcommands.newline_join", new=MagicMock())
    def test__resume_session_fail_non_blocker(self, memory_job_result_mock):
        self_mock = MagicMock()
        self_mock.ctx.sa.get_job_state.return_value.effective_certification_status = (
            "non-blocker"
        )

        session_metadata_mock = self_mock.ctx.sa.resume_session.return_value
        session_metadata_mock.flags = ["testplanless"]

        resume_params_mock = MagicMock()
        resume_params_mock.action = "fail"

        Launcher._resume_session(self_mock, resume_params_mock)

        args, _ = memory_job_result_mock.call_args_list[-1]
        result_dict, *_ = args
        self.assertEqual(result_dict["outcome"], IJobResult.OUTCOME_FAIL)

    @patch("checkbox_ng.launcher.subcommands.MemoryJobResult")
    @patch("checkbox_ng.launcher.subcommands.newline_join", new=MagicMock())
    def test__resume_session_skip_blocker(self, memory_job_result_mock):
        self_mock = MagicMock()
        self_mock.ctx.sa.get_job_state.return_value.effective_certification_status = (
            "blocker"
        )

        session_metadata_mock = self_mock.ctx.sa.resume_session.return_value
        session_metadata_mock.flags = ["testplanless"]

        resume_params_mock = MagicMock()
        resume_params_mock.action = "skip"

        Launcher._resume_session(self_mock, resume_params_mock)

        args, _ = memory_job_result_mock.call_args_list[-1]
        result_dict, *_ = args
        self.assertEqual(result_dict["outcome"], IJobResult.OUTCOME_SKIP)

    @patch("checkbox_ng.launcher.subcommands.MemoryJobResult")
    @patch("checkbox_ng.launcher.subcommands.newline_join", new=MagicMock())
    def test__resume_session_skip_non_blocker(self, memory_job_result_mock):
        self_mock = MagicMock()
        self_mock.ctx.sa.get_job_state.return_value.effective_certification_status = (
            "non-blocker"
        )

        session_metadata_mock = self_mock.ctx.sa.resume_session.return_value
        session_metadata_mock.flags = ["testplanless"]

        resume_params_mock = MagicMock()
        resume_params_mock.action = "skip"

        Launcher._resume_session(self_mock, resume_params_mock)

        args, _ = memory_job_result_mock.call_args_list[-1]
        result_dict, *_ = args
        self.assertEqual(result_dict["outcome"], IJobResult.OUTCOME_SKIP)

    @patch("checkbox_ng.launcher.subcommands.MemoryJobResult")
    @patch("checkbox_ng.launcher.subcommands.newline_join", new=MagicMock())
    def test__resume_session_rerun(self, memory_job_result_mock):
        self_mock = MagicMock()
        self_mock.ctx.sa.get_job_state.return_value.effective_certification_status = (
            "non-blocker"
        )

        session_metadata_mock = self_mock.ctx.sa.resume_session.return_value
        session_metadata_mock.flags = ["testplanless"]

        resume_params_mock = MagicMock()
        resume_params_mock.action = "rerun"

        Launcher._resume_session(self_mock, resume_params_mock)

        # we don't use job result of rerun jobs
        self.assertFalse(self_mock.ctx.sa.use_job_result.called)

    @patch("checkbox_ng.launcher.subcommands.load_configs")
    @patch("checkbox_ng.launcher.subcommands.Colorizer", new=MagicMock())
    def test_invoked_resume(self, load_config_mock):
        self_mock = MagicMock()
        self_mock._maybe_auto_resume_session.return_value = [False, True]
        self_mock._start_new_session.side_effect = ResumeInstead()

        ctx_mock = MagicMock()
        ctx_mock.args.verify = False
        ctx_mock.args.version = False
        ctx_mock.args.verbose = False
        ctx_mock.args.debug = False
        ctx_mock.sa.get_resumable_sessions.return_value = []
        ctx_mock.sa.get_static_todo_list.return_value = False

        load_config_mock.return_value.get_value.return_value = "normal"

        Launcher.invoked(self_mock, ctx_mock)


class TestLauncherReturnCodes(TestCase):
    def setUp(self):
        self.launcher = Launcher()
        self.launcher._maybe_rerun_jobs = Mock(return_value=False)
        self.launcher._maybe_auto_resume_session = Mock(return_value=False)
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


class TestLListBootstrapped(TestCase):
    def setUp(self):
        self.launcher = ListBootstrapped()
        self.ctx = Mock()
        self.ctx.args = Mock(TEST_PLAN="", format="")
        self.ctx.sa = Mock(
            start_new_session=Mock(),
            get_test_plans=Mock(
                return_value=["test-plan1", "test-plan2"]),
            select_test_plan=Mock(),
            bootstrap=Mock(),
            get_static_todo_list=Mock(
                return_value=["test-job1", "test-job2"]),
            get_job=Mock(
                side_effect=[
                    Mock(
                        _raw_data={
                            "id": "namespace1::test-job1",
                            "summary": "fake-job1",
                            "plugin": "manual",
                            "description": "fake-description1",
                            "certification_status": "unspecified"
                        },
                        id="namespace1::test-job1",
                        partial_id="test-job1"
                    ),
                    Mock(
                        _raw_data={
                            "id": "namespace2::test-job2",
                            "summary": "fake-job2",
                            "plugin": "shell",
                            "command": "ls",
                            "certification_status": "unspecified"
                        },
                        id="namespace2::test-job2",
                        partial_id="test-job2"
                    ),
                ]
            ),
            get_job_state=Mock(
                return_value=Mock(effective_certification_status="blocker")),
            get_resumable_sessions=Mock(return_value=[]),
            get_dynamic_todo_list=Mock(return_value=[]),
        )

    def test_invoke_test_plan_not_found(self):
        self.ctx.args.TEST_PLAN = "test-plan3"

        with self.assertRaisesRegex(SystemExit, "Test plan not found"):
            self.launcher.invoked(self.ctx)

    @patch("sys.stdout", new_callable=StringIO)
    def test_invoke_print_output_format(self, stdout):
        self.ctx.args.TEST_PLAN = "test-plan1"
        self.ctx.args.format = "?"

        expected_out = (
            "Available fields are:\ncertification_status, command, "
            "description, full_id, id, plugin, summary\n"
        )
        self.launcher.invoked(self.ctx)
        self.assertEqual(stdout.getvalue(), expected_out)

    @patch("sys.stdout", new_callable=StringIO)
    def test_invoke_print_output_standard_format(self, stdout):
        self.ctx.args.TEST_PLAN = "test-plan1"
        self.ctx.args.format = "{full_id}\n"

        expected_out = (
            "namespace1::test-job1\n"
            "namespace2::test-job2\n"
        )
        self.launcher.invoked(self.ctx)
        self.assertEqual(stdout.getvalue(), expected_out)

    @patch("sys.stdout", new_callable=StringIO)
    def test_invoke_print_output_customized_format(self, stdout):
        self.ctx.args.TEST_PLAN = "test-plan1"
        self.ctx.args.format = (
            "id: {id}\nplugin: {plugin}\nsummary: {summary}\n"
            "certification blocker: {certification_status}\n\n"
        )

        expected_out = (
            "id: test-job1\n"
            "plugin: manual\n"
            "summary: fake-job1\n"
            "certification blocker: blocker\n\n"
            "id: test-job2\n"
            "plugin: shell\n"
            "summary: fake-job2\n"
            "certification blocker: blocker\n\n"
        )
        self.launcher.invoked(self.ctx)
        self.assertEqual(stdout.getvalue(), expected_out)
