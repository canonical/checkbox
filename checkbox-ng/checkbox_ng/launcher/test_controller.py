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


import socket
import json

from unittest import TestCase, mock
from functools import partial

from checkbox_ng.urwid_ui import ResumeInstead
from checkbox_ng.launcher.controller import RemoteController
from checkbox_ng.launcher.controller import is_hostname_a_loopback


class TestRemoteController(TestCase):
    @mock.patch("checkbox_ng.launcher.controller.is_hostname_a_loopback")
    @mock.patch("time.time")
    @mock.patch("builtins.print")
    @mock.patch("os.path.exists")
    @mock.patch("checkbox_ng.launcher.controller.Configuration.from_text")
    @mock.patch("checkbox_ng.launcher.controller._")
    # used to load an empty launcher with no error
    def test_invoked_ok(
        self,
        gettext_mock,
        configuration_mock,
        path_exists_mock,
        print_mock,
        time_mock,
        loopback_check,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.launcher = "example"
        ctx_mock.args.user = "some username"
        ctx_mock.args.host = "undertest@local"
        ctx_mock.args.port = "9999"
        loopback_check.return_value = False

        self_mock = mock.MagicMock()

        # make the check if launcher is there go through
        path_exists_mock.return_value = True
        # avoid monitoring time (no timeout in this test)
        time_mock.return_value = 0

        with mock.patch("builtins.open") as mm:
            mm.return_value = mm
            mm.read.return_value = "[launcher]\nversion=0"
            RemoteController.invoked(self_mock, ctx_mock)

        self.assertTrue(self_mock.connect_and_run.called)

    @mock.patch("checkbox_ng.launcher.controller.is_hostname_a_loopback")
    @mock.patch("time.time")
    @mock.patch("builtins.print")
    @mock.patch("os.path.exists")
    @mock.patch("checkbox_ng.launcher.controller.Configuration.from_text")
    @mock.patch("checkbox_ng.launcher.controller._")
    def test_invoked_ok_for_localhost(
        self,
        gettext_mock,
        configuration_mock,
        path_exists_mock,
        print_mock,
        time_mock,
        loopback_check,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.launcher = "example"
        ctx_mock.args.user = "some username"
        ctx_mock.args.host = "undertest@local"
        ctx_mock.args.port = "9999"
        loopback_check.return_value = True

        self_mock = mock.MagicMock()

        # make the check if launcher is there go through
        path_exists_mock.return_value = True
        # avoid monitoring time (no timeout in this test)
        time_mock.return_value = 0

        with mock.patch("builtins.open") as mm:
            mm.return_value = mm
            mm.read.return_value = "[launcher]\nversion=0"
            RemoteController.invoked(self_mock, ctx_mock)

        self.assertTrue(self_mock.connect_and_run.called)

    @mock.patch("checkbox_ng.launcher.controller.is_hostname_a_loopback")
    @mock.patch("time.time")
    @mock.patch("time.sleep")
    @mock.patch("builtins.print")
    @mock.patch("checkbox_ng.launcher.controller.Configuration.from_text")
    @mock.patch("checkbox_ng.launcher.controller._")
    def test_invoked_err_timeout(
        self,
        gettext_mock,
        configuration_mock,
        print_mock,
        time_sleep_mock,
        time_mock,
        loopback_check,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.launcher = None
        ctx_mock.args.user = "some username"
        ctx_mock.args.host = "undertest@local"
        ctx_mock.args.port = "9999"
        loopback_check.return_value = True

        self_mock = mock.MagicMock()
        self_mock.connect_and_run.side_effect = ConnectionRefusedError

        # intentionally cause the timeout
        # we do 1 iteration, then we blow up due to timeout
        time_mock.side_effect = [0, 0, 2e10]

        with self.assertRaises(SystemExit):
            RemoteController.invoked(self_mock, ctx_mock)

    @mock.patch("checkbox_ng.launcher.controller.RemoteSessionAssistant")
    def test_check_remote_api_match_ok(self, remote_assistant_mock):
        """
        Test that the check_remote_api_match function does not fail/crash
        if the two versions match
        """
        self_mock = mock.MagicMock()
        session_assistant_mock = mock.MagicMock()
        self_mock.sa = session_assistant_mock

        remote_assistant_mock.REMOTE_API_VERSION = 0
        session_assistant_mock.get_remote_api_version.return_value = 0

        RemoteController.check_remote_api_match(self_mock)

    @mock.patch("checkbox_ng.launcher.controller.RemoteSessionAssistant")
    def test_check_remote_api_match_fail(self, remote_assistant_mock):
        """
        Test that the check_remote_api_match function exits checkbox
        if the two versions don't match
        """
        self_mock = mock.MagicMock()
        session_assistant_mock = mock.MagicMock()
        self_mock.sa = session_assistant_mock

        remote_assistant_mock.REMOTE_API_VERSION = 1
        session_assistant_mock.get_remote_api_version.return_value = 0

        with self.assertRaises(SystemExit):
            # this should exit checkbox because the two versions are different
            RemoteController.check_remote_api_match(self_mock)

        remote_assistant_mock.REMOTE_API_VERSION = 0
        session_assistant_mock.get_remote_api_version.return_value = 1

        with self.assertRaises(SystemExit):
            # this should also exit checkbox because the two versions are
            # different
            RemoteController.check_remote_api_match(self_mock)

    def test_finish_session_all_pass(self):
        """
        Check if the finish_session function properly computes the
        `_has_anything_failed` flag when all jobs pass.
        """
        self_mock = mock.MagicMock()

        self_mock.sa.has_any_job_failed.return_value = False

        RemoteController.finish_session(self_mock)

        self.assertFalse(self_mock._has_anything_failed)

    def test_finish_session_with_failure(self):
        """
        Check if the finish_session function properly computes the
        `_has_anything_failed` flag when a job fails.
        """
        self_mock = mock.MagicMock()

        mock_job_state_map = {
            "job1": mock.MagicMock(result=mock.MagicMock(outcome="pass")),
            "job2": mock.MagicMock(result=mock.MagicMock(outcome="fail")),
            "job3": mock.MagicMock(result=mock.MagicMock(outcome="pass")),
        }
        self_mock.manager.default_device_context._state._job_state_map = (
            mock_job_state_map
        )
        RemoteController.finish_session(self_mock)

        self.assertTrue(self_mock._sa._has_anything_failed)

    def test_finish_session_with_crash(self):
        """
        Check if the finish_session function properly computes the
        `_has_anything_failed` flag when a job crashes.
        """
        self_mock = mock.MagicMock()

        mock_job_state_map = {
            "job1": mock.MagicMock(result=mock.MagicMock(outcome="pass")),
            "job2": mock.MagicMock(result=mock.MagicMock(outcome="crash")),
            "job3": mock.MagicMock(result=mock.MagicMock(outcome="pass")),
        }
        self_mock.manager.default_device_context._state._job_state_map = (
            mock_job_state_map
        )
        RemoteController.finish_session(self_mock)

        self.assertTrue(self_mock._sa._has_anything_failed)

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    @mock.patch("checkbox_ng.launcher.controller.resume_dialog")
    def test__handle_last_job_after_resume_when_silent(self, res_dia_mock, _):
        self_mock = mock.MagicMock()
        self_mock.launcher = mock.MagicMock()
        self_mock.launcher.get_value.return_value = "silent"
        self_mock.sa.get_jobs_repr.return_value = [
            {"name": "job", "category_name": "category", "id": "job_id"}
        ]
        with mock.patch("json.loads") as _:
            with mock.patch("builtins.print") as print_mock:
                RemoteController._handle_last_job_after_resume(
                    self_mock, {"last_job": "job_id"}
                )

        self.assertFalse(res_dia_mock.called)

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    @mock.patch("checkbox_ng.launcher.controller.resume_dialog")
    def test__handle_last_job_after_resume_when_not_silent(
        self, res_dia_mock, _
    ):
        self_mock = mock.MagicMock()
        self_mock.launcher = mock.MagicMock()
        self_mock.launcher.get_value.return_value = "loud"
        self_mock.sa.get_jobs_repr.return_value = [
            {"name": "job", "category_name": "category", "id": "job_id"}
        ]
        with mock.patch("json.loads") as _:
            with mock.patch("builtins.print") as print_mock:
                RemoteController._handle_last_job_after_resume(
                    self_mock, {"last_job": "job_id"}
                )

        self.assertTrue(res_dia_mock.called)

    def test_restart(self):
        self_mock = mock.MagicMock()

        RemoteController.restart(self_mock)

        # restarting a controller means abandoning the current session
        # and get the possibility to start/resume another

        self.assertTrue(self_mock.abandon.called)
        self.assertTrue(self_mock.resume_or_start_new_session.called)

    def test_resume_or_start_new_session_interactive(self):
        self_mock = mock.MagicMock()
        self_mock.should_start_via_autoresume.return_value = False
        self_mock.should_start_via_launcher.return_value = False

        RemoteController.resume_or_start_new_session(self_mock)

        self.assertTrue(self_mock.interactively_choose_tp.called)
        self.assertTrue(self_mock.run_jobs.called)

    def test_resume_or_start_new_session_auto_last_session(self):
        self_mock = mock.MagicMock()
        self_mock.should_start_via_autoresume.return_value = True
        self_mock.should_start_via_launcher.return_value = False

        RemoteController.resume_or_start_new_session(self_mock)

        self.assertTrue(self_mock.automatically_resume_last_session.called)
        self.assertTrue(self_mock.run_jobs.called)

    def test_resume_or_start_new_session_auto_launcher(self):
        self_mock = mock.MagicMock()
        self_mock.should_start_via_autoresume.return_value = False
        self_mock.should_start_via_launcher.return_value = True

        RemoteController.resume_or_start_new_session(self_mock)

        self.assertTrue(self_mock.automatically_start_via_launcher.called)
        self.assertTrue(self_mock.run_jobs.called)

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_description_command_none(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "description"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": None,
            "num": 0,
            "name": "name",
            "category_name": "category",
        }
        simple_ui_mock().wait_for_interaction_prompt.return_value = "skip"

        RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_description_skip(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "description"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": "skip_description",
            "num": 0,
            "name": "name",
            "category_name": "category",
        }
        simple_ui_mock().wait_for_interaction_prompt.return_value = "skip"

        RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_description_enter(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "description"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": "skip_description",
            "num": 0,
            "name": "name",
            "category_name": "category",
        }
        simple_ui_mock().wait_for_interaction_prompt.return_value = ""

        RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_description_quit(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "description"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": "quit_description",
            "num": 0,
            "name": "name",
            "category_name": "category",
        }
        simple_ui_mock().wait_for_interaction_prompt.return_value = "quit"

        with self.assertRaises(SystemExit):
            RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_steps_run(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "steps"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": None,
            "num": 0,
            "name": "name",
            "category_name": "category",
        }

        RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_steps_enter(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "steps"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": "skip_description",
            "num": 0,
            "name": "name",
            "category_name": "category",
        }
        simple_ui_mock().wait_for_interaction_prompt.return_value = ""

        RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_steps_skip(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "steps"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": "skip_description",
            "num": 0,
            "name": "name",
            "category_name": "category",
        }
        simple_ui_mock().wait_for_interaction_prompt.return_value = "skip"

        RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test__run_jobs_steps_quit(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        interaction_mock = mock.MagicMock()
        interaction_mock.kind = "steps"

        self_mock.sa.run_job.return_value = [interaction_mock]
        jobs_repr_mock = {
            "id": "id_mock",
            "command": "quit_description",
            "num": 0,
            "name": "name",
            "category_name": "category",
        }
        simple_ui_mock().wait_for_interaction_prompt.return_value = "quit"

        with self.assertRaises(SystemExit):
            RemoteController._run_jobs(self_mock, [jobs_repr_mock])

    @mock.patch(
        "checkbox_ng.launcher.controller.generate_resume_candidate_description",
        new=mock.MagicMock(),
    )
    @mock.patch("checkbox_ng.launcher.controller.ResumeMenu")
    def test_delete_session(self, mock_menu):
        self_mock = mock.MagicMock()
        resumable_sessions = [
            mock.MagicMock(id=1, name="Session 1"),
            mock.MagicMock(id=2, name="Session 2"),
        ]
        menu_actions_buffer = [
            mock.MagicMock(
                action="delete", session_id=1
            ),  # First call simulates deletion
            mock.MagicMock(
                action="resume", session_id=2
            ),  # Second call simulates resuming a session
        ]
        # Setup the mock to simulate delete action
        mock_menu.return_value.run.side_effect = menu_actions_buffer

        self_mock.sa.get_resumable_sessions.return_value = resumable_sessions[
            1:
        ]

        resumed = RemoteController._resume_session_menu(
            self_mock, resumable_sessions
        )

        # Check if the session was resumed correctly after deletion
        self.assertTrue(resumed)
        self_mock._resume_session.assert_called_once_with(
            menu_actions_buffer[1]
        )
        self_mock.sa.delete_sessions.assert_called_once_with([1])

    @mock.patch(
        "checkbox_ng.launcher.controller.generate_resume_candidate_description",
        new=mock.MagicMock(),
    )
    @mock.patch("checkbox_ng.launcher.controller.ResumeMenu")
    def test_no_session_resumed(self, mock_menu):
        self_mock = mock.MagicMock()
        resumable_sessions = [
            mock.MagicMock(id=1, name="Session 1"),
            mock.MagicMock(id=2, name="Session 2"),
        ]
        menu_actions_buffer = [
            mock.MagicMock(
                action="delete", session_id=1
            ),  # First call simulates deletion
            mock.MagicMock(
                action="resume", session_id=2
            ),  # Second call simulates resuming a session
        ]
        # Setup the mock to simulate delete action
        mock_menu.return_value.run.side_effect = menu_actions_buffer

        self_mock.sa.get_resumable_sessions.return_value = []

        resumed = RemoteController._resume_session_menu(
            self_mock, [resumable_sessions[0]]
        )

        # Check that the method returns False when all sessions are deleted
        self.assertFalse(resumed)

    @mock.patch(
        "checkbox_ng.launcher.controller.generate_resume_candidate_description",
        new=mock.MagicMock(),
    )
    @mock.patch("checkbox_ng.launcher.controller.ResumeMenu")
    def test_session_resumed_no_id(self, mock_menu):
        self_mock = mock.MagicMock()
        resumable_sessions = [
            mock.MagicMock(id=1, name="Session 1"),
            mock.MagicMock(id=2, name="Session 2"),
        ]
        # Setup the mock to simulate selecting a session to resume
        mock_menu.return_value.run.return_value = mock.MagicMock(
            action="resume", session_id=None
        )

        resumed = RemoteController._resume_session_menu(
            self_mock, resumable_sessions
        )

        # Check that the method returns True when a session is resumed
        self.assertFalse(resumed)
        self.assertFalse(self_mock._resume_session.called)

    @mock.patch(
        "checkbox_ng.launcher.controller.generate_resume_candidate_description",
        new=mock.MagicMock(),
    )
    @mock.patch("checkbox_ng.launcher.controller.ResumeMenu")
    def test_session_resumed(self, mock_menu):
        self_mock = mock.MagicMock()
        resumable_sessions = [
            mock.MagicMock(id=1, name="Session 1"),
            mock.MagicMock(id=2, name="Session 2"),
        ]
        # Setup the mock to simulate selecting a session to resume
        mock_menu.return_value.run.return_value = mock.MagicMock(
            action="resume", session_id=2
        )

        resumed = RemoteController._resume_session_menu(
            self_mock, resumable_sessions
        )

        # Check that the method returns True when a session is resumed
        self.assertTrue(resumed)
        self.assertTrue(self_mock._resume_session.called)

    @mock.patch("json.loads")
    @mock.patch("builtins.open")
    @mock.patch("checkbox_ng.launcher.controller.IJobResult")
    @mock.patch(
        "checkbox_ng.launcher.controller.request_comment",
        new=mock.MagicMock(),
    )
    def test_resume_session_pass(
        self,
        mock_IJobResult,
        mock_open,
        mock_loads,
    ):
        mock_loads.return_value = {"testplan_id": "abc"}

        sa_mock = mock.MagicMock()
        resume_params = mock.MagicMock(
            action="pass", session_id="123", comments="Initial comment"
        )
        metadata_mock = mock.MagicMock(
            app_blob=b'{"testplan_id": "abc"}',
            flags=[],
            running_job_name="job1",
        )
        sa_mock.resume_session.return_value = metadata_mock
        sa_mock.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="non-blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock.resume_session.assert_called_once_with("123")
        sa_mock.select_test_plan.assert_called_once_with("abc")
        self.assertTrue(sa_mock.bootstrap.called)
        sa_mock.resume_by_id.assert_called_once_with(
            "123",
            {
                "comments": "Initial comment\nPassed after resuming execution",
                "outcome": mock_IJobResult.OUTCOME_PASS,
            },
        )

    @mock.patch("json.loads")
    @mock.patch("builtins.open")
    @mock.patch("checkbox_ng.launcher.controller.IJobResult")
    @mock.patch(
        "checkbox_ng.launcher.controller.request_comment",
        new=mock.MagicMock(return_value="comment requested from user"),
    )
    def test_resume_session_fail_not_cert_blocker(
        self,
        mock_IJobResult,
        mock_open,
        mock_loads,
    ):
        mock_loads.return_value = {"testplan_id": "abc"}

        sa_mock = mock.MagicMock()
        resume_params = mock.MagicMock(
            action="fail", session_id="123", comments="Initial comment"
        )
        metadata_mock = mock.MagicMock(
            app_blob=b'{"testplan_id": "abc"}',
            flags=[],
            running_job_name="job1",
        )
        sa_mock.resume_session.return_value = metadata_mock
        sa_mock.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="non-blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock.resume_session.assert_called_once_with("123")
        sa_mock.select_test_plan.assert_called_once_with("abc")
        self.assertTrue(sa_mock.bootstrap.called)
        sa_mock.resume_by_id.assert_called_once_with(
            "123",
            {
                "comments": "Initial comment\nFailed after resuming execution",
                "outcome": mock_IJobResult.OUTCOME_FAIL,
            },
        )

    @mock.patch("json.loads")
    @mock.patch("builtins.open")
    @mock.patch("checkbox_ng.launcher.controller.IJobResult")
    @mock.patch(
        "checkbox_ng.launcher.controller.request_comment",
        new=mock.MagicMock(return_value="comment requested from user"),
    )
    def test_resume_session_fail_cert_blocker(
        self,
        mock_IJobResult,
        mock_open,
        mock_loads,
    ):
        mock_loads.return_value = {"testplan_id": "abc"}

        sa_mock = mock.MagicMock()
        resume_params = mock.MagicMock(
            action="fail", session_id="123", comments=None
        )
        metadata_mock = mock.MagicMock(
            app_blob=b'{"testplan_id": "abc"}',
            flags=["testplanless"],
            running_job_name="job1",
        )
        sa_mock.resume_session.return_value = metadata_mock
        sa_mock.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock.resume_session.assert_called_once_with("123")
        sa_mock.resume_by_id.assert_called_once_with(
            "123",
            {
                "comments": "comment requested from user",
                "outcome": mock_IJobResult.OUTCOME_FAIL,
            },
        )

    @mock.patch("json.loads")
    @mock.patch("builtins.open")
    @mock.patch("checkbox_ng.launcher.controller.IJobResult")
    @mock.patch(
        "checkbox_ng.launcher.controller.request_comment",
        new=mock.MagicMock(return_value="comment requested from user"),
    )
    def test_resume_session_skip_not_cert_blocker(
        self,
        mock_IJobResult,
        mock_open,
        mock_loads,
    ):
        mock_loads.return_value = {"testplan_id": "abc"}

        sa_mock = mock.MagicMock()
        resume_params = mock.MagicMock(
            action="skip", session_id="123", comments="Initial comment"
        )
        metadata_mock = mock.MagicMock(
            app_blob=b'{"testplan_id": "abc"}',
            flags=[],
            running_job_name="job1",
        )
        sa_mock.resume_session.return_value = metadata_mock
        sa_mock.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="non-blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock.resume_session.assert_called_once_with("123")
        sa_mock.select_test_plan.assert_called_once_with("abc")
        self.assertTrue(sa_mock.bootstrap.called)
        sa_mock.resume_by_id.assert_called_once_with(
            "123",
            {
                "comments": "Initial comment\nSkipped after resuming execution",
                "outcome": mock_IJobResult.OUTCOME_SKIP,
            },
        )

    @mock.patch("json.loads")
    @mock.patch("builtins.open")
    @mock.patch("checkbox_ng.launcher.controller.IJobResult")
    @mock.patch(
        "checkbox_ng.launcher.controller.request_comment",
        new=mock.MagicMock(return_value="comment requested from user"),
    )
    def test_resume_session_skip_cert_blocker(
        self,
        mock_IJobResult,
        mock_open,
        mock_loads,
    ):
        mock_loads.return_value = {"testplan_id": "abc"}

        sa_mock = mock.MagicMock()
        resume_params = mock.MagicMock(
            action="skip", session_id="123", comments=None
        )
        metadata_mock = mock.MagicMock(
            app_blob=b'{"testplan_id": "abc"}',
            flags=["testplanless"],
            running_job_name="job1",
        )
        sa_mock.resume_session.return_value = metadata_mock
        sa_mock.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock.resume_session.assert_called_once_with("123")
        sa_mock.resume_by_id.assert_called_once_with(
            "123",
            {
                "comments": "comment requested from user",
                "outcome": mock_IJobResult.OUTCOME_SKIP,
            },
        )

    @mock.patch("json.loads")
    @mock.patch("builtins.open")
    @mock.patch("checkbox_ng.launcher.controller.IJobResult")
    @mock.patch(
        "checkbox_ng.launcher.controller.request_comment",
        new=mock.MagicMock(return_value="comment requested from user"),
    )
    def test_resume_session_rerun(
        self,
        mock_IJobResult,
        mock_open,
        mock_loads,
    ):
        mock_loads.return_value = {"testplan_id": "abc"}

        sa_mock = mock.MagicMock()
        resume_params = mock.MagicMock(
            action="rerun", session_id="123", comments=None
        )
        metadata_mock = mock.MagicMock(
            app_blob=b'{"testplan_id": "abc"}',
            flags=["testplanless"],
            running_job_name="job1",
        )
        sa_mock.resume_session.return_value = metadata_mock
        sa_mock.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock.resume_session.assert_called_once_with("123")
        sa_mock.resume_by_id.assert_called_once_with(
            "123",
            {
                "comments": None,
                "outcome": None,
            },
        )

    def test_should_start_via_launcher_true(self):
        self_mock = mock.MagicMock()

        def get_value_mock(top_level, attribute):
            if top_level == "test plan":
                if attribute == "forced":
                    return True
                elif attribute == "unit":
                    return "tp_unit_id"
            return mock.MagicMock()

        self_mock.launcher.get_value = get_value_mock

        self.assertTrue(RemoteController.should_start_via_launcher(self_mock))

    def test_should_start_via_launcher_false(self):
        self_mock = mock.MagicMock()

        def get_value_mock(top_level, attribute):
            if top_level == "test plan":
                if attribute == "forced":
                    return False
                elif attribute == "unit":
                    return "tp_unit_id"
            return mock.MagicMock()

        self_mock.launcher.get_value = get_value_mock

        self.assertFalse(RemoteController.should_start_via_launcher(self_mock))

    def test_should_start_via_launcher_exit(self):
        self_mock = mock.MagicMock()

        def get_value_mock(top_level, attribute):
            if top_level == "test plan":
                if attribute == "forced":
                    return True
                elif attribute == "unit":
                    return None
            return mock.MagicMock()

        self_mock.launcher.get_value = get_value_mock
        with self.assertRaises(SystemExit):
            RemoteController.should_start_via_launcher(self_mock)

    def test_interactively_choose_tp(self):
        self_mock = mock.MagicMock()

        # by default always try to start a new session and not resuming
        RemoteController.interactively_choose_tp(self_mock)

        self.assertTrue(self_mock._new_session_flow.called)
        self.assertFalse(self_mock._resume_session_menu.called)

    def test_interactively_choose_tp_resume(self):
        self_mock = mock.MagicMock()
        self_mock._new_session_flow.side_effect = ResumeInstead
        self_mock._resume_session_menu.return_value = True

        RemoteController.interactively_choose_tp(self_mock)

        self.assertTrue(self_mock._new_session_flow.called)
        self.assertTrue(self_mock._resume_session_menu.called)

    def test_interactively_choose_tp_resume_retry_tp(self):
        self_mock = mock.MagicMock()
        self_mock._new_session_flow.side_effect = [ResumeInstead, True]
        self_mock._resume_session_menu.return_value = True

        RemoteController.interactively_choose_tp(self_mock)

        self.assertTrue(self_mock._new_session_flow.called)
        self.assertTrue(self_mock._resume_session_menu.called)

    def test__resumed_session(self):
        self_mock = mock.MagicMock()

        with RemoteController._resumed_session(
            self_mock, "session_id"
        ) as metadata:
            self.assertEqual(
                self_mock.sa.resume_session.return_value, metadata
            )
        self.assertTrue(self_mock.sa.resume_session.called)
        self.assertTrue(self_mock.sa.abandon_session.called)

    def test_should_start_via_autoresume_true(self):
        last_session_mock = mock.MagicMock()
        self_mock = mock.MagicMock()
        self_mock.sa.get_resumable_sessions.return_value = iter(
            [last_session_mock]
        )

        self_mock._resumed_session = partial(
            RemoteController._resumed_session, self_mock
        )
        metadata = self_mock.sa.resume_session()
        metadata.app_blob = b"""
            {
                "testplan_id" : "testplan_id"
            }
        """
        metadata.running_job_name = "job_id"

        self_mock.sa.get_job_state.return_value.job.plugin = "shell"

        self.assertTrue(
            RemoteController.should_start_via_autoresume(self_mock)
        )

        self.assertTrue(self_mock.sa.select_test_plan.called)
        self.assertTrue(self_mock.sa.bootstrap.called)

    def test_should_start_via_autoresume_no_resumable_sessions(self):
        self_mock = mock.MagicMock()
        self_mock.sa.get_resumable_sessions.return_value = iter(
            []
        )  # No resumable sessions

        self.assertFalse(
            RemoteController.should_start_via_autoresume(self_mock)
        )

    def test_should_start_via_autoresume_no_testplan_id_in_app_blob(self):
        self_mock = mock.MagicMock()
        last_session_mock = mock.MagicMock()
        self_mock.sa.get_resumable_sessions.return_value = iter(
            [last_session_mock]
        )

        self_mock._resumed_session = partial(
            RemoteController._resumed_session, self_mock
        )
        metadata = self_mock.sa.resume_session()
        metadata.app_blob = b"{}"

        self.assertFalse(
            RemoteController.should_start_via_autoresume(self_mock)
        )
        self.assertTrue(self_mock.sa.abandon_session.called)

    def test_should_start_via_autoresume_no_running_job_name(self):
        self_mock = mock.MagicMock()
        last_session_mock = mock.MagicMock()
        self_mock.sa.get_resumable_sessions.return_value = iter(
            [last_session_mock]
        )

        self_mock._resumed_session = partial(
            RemoteController._resumed_session, self_mock
        )
        metadata = self_mock.sa.resume_session()
        metadata.app_blob = b'{"testplan_id" : "testplan_id"}'
        metadata.running_job_name = ""

        self.assertFalse(
            RemoteController.should_start_via_autoresume(self_mock)
        )

    def test_should_start_via_autoresume_job_plugin_not_shell(self):
        self_mock = mock.MagicMock()
        last_session_mock = mock.MagicMock()
        self_mock.sa.get_resumable_sessions.return_value = iter(
            [last_session_mock]
        )

        self_mock._resumed_session = partial(
            RemoteController._resumed_session, self_mock
        )
        metadata = self_mock.sa.resume_session()
        metadata.app_blob = b'{"testplan_id" : "testplan_id"}'
        metadata.running_job_name = "job_id"

        job_state_mock = mock.MagicMock()
        job_state_mock.job.plugin = "user-interact"
        self_mock.sa.get_job_state.return_value = job_state_mock

        self.assertFalse(
            RemoteController.should_start_via_autoresume(self_mock)
        )

    def test_automatically_start_via_launcher(self):
        self_mock = mock.MagicMock()

        RemoteController.automatically_start_via_launcher(self_mock)

        self.assertTrue(self_mock.select_tp.called)
        self.assertTrue(self_mock.select_jobs.called)

    def test_automatically_resume_last_session(self):
        self_mock = mock.MagicMock()

        RemoteController.automatically_resume_last_session(self_mock)

        self.assertTrue(self_mock.sa.get_resumable_sessions.called)
        self.assertTrue(self_mock.sa.resume_by_id.called)

    def test_start_session_success(self):
        self_mock = mock.MagicMock()
        self_mock._launcher_text = "launcher_example"
        self_mock._normal_user = True
        expected_configuration = {
            "launcher": "launcher_example",
            "normal_user": True,
        }

        self_mock.sa.start_session_json.return_value = '["testplan1"]'

        tps = RemoteController.start_session(self_mock)

        self_mock.sa.start_session_json.assert_called_once_with(
            json.dumps(expected_configuration)
        )
        self.assertEqual(tps, ["testplan1"])

    def test_start_session_with_sideloaded_providers(self):
        self_mock = mock.MagicMock()
        self_mock._launcher_text = "launcher_example"
        self_mock._normal_user = True
        self_mock.sa.sideloaded_providers = True

        self_mock.sa.start_session_json.return_value = '["testplan1"]'

        RemoteController.start_session(self_mock)

    def test_start_session_runtime_error(self):
        self_mock = mock.MagicMock()
        self_mock._launcher_text = "launcher_example"
        self_mock._normal_user = True
        self_mock.sa.start_session_json.side_effect = RuntimeError(
            "Failed to start session"
        )

        with self.assertRaises(SystemExit) as _:
            RemoteController.start_session(self_mock)

    @mock.patch("checkbox_ng.launcher.controller.ManifestBrowser")
    def test__save_manifest_interactive_with_visible_manifests(
        self, mock_browser_class
    ):
        controller = RemoteController()
        sa_mock = mock.MagicMock()
        controller._sa = sa_mock

        manifest_repr = {
            "section1": [
                {"id": "visible1", "value": 0, "hidden": False},
                {"id": "visible2", "value": False, "hidden": False},
            ]
        }
        sa_mock.get_manifest_repr_json.return_value = json.dumps(manifest_repr)

        mock_browser = mock.MagicMock()
        mock_browser.run.return_value = {
            "visible1": 5,
            "visible2": True,
        }
        mock_browser_class.return_value = mock_browser
        mock_browser_class.has_visible_manifests.return_value = True

        controller._save_manifest(interactive=True)

        sa_mock.save_manifest_json.assert_called_with(
            json.dumps({"visible1": 5, "visible2": True})
        )

    @mock.patch("checkbox_ng.launcher.controller.ManifestBrowser")
    def test__save_manifest_interactive_no_visible_manifests(
        self, mock_browser_class
    ):
        controller = RemoteController()
        sa_mock = mock.MagicMock()
        controller._sa = sa_mock

        manifest_repr = {
            "section1": [
                {"id": "hidden1", "value": True, "hidden": True},
                {"id": "hidden2", "value": 2, "hidden": True},
            ]
        }
        sa_mock.get_manifest_repr_json.return_value = json.dumps(manifest_repr)
        mock_browser_class.has_visible_manifests.return_value = False
        mock_browser_class.get_flattened_values.return_value = {
            "hidden1": True,
            "hidden2": 2,
        }

        controller._save_manifest(interactive=True)

        self.assertEqual(mock_browser_class.call_count, 0)
        self.assertEqual(
            mock_browser_class.has_visible_manifests.call_count, 1
        )
        self.assertEqual(mock_browser_class.get_flattened_values.call_count, 1)
        self.assertEqual(sa_mock.save_manifest_json.call_count, 1)
        sa_mock.save_manifest_json.assert_called_with(
            json.dumps({"hidden1": True, "hidden2": 2})
        )

    @mock.patch("checkbox_ng.launcher.controller.ManifestBrowser")
    def test__save_manifest_non_interactive(self, mock_browser_class):
        controller = RemoteController()
        sa_mock = mock.MagicMock()
        controller._sa = sa_mock

        manifest_repr = {
            "section1": [
                {"id": "manifest1", "value": False, "hidden": False},
                {"id": "manifest2", "value": 7, "hidden": True},
            ]
        }
        sa_mock.get_manifest_repr_json.return_value = json.dumps(manifest_repr)
        mock_browser_class.get_flattened_values.return_value = {
            "manifest1": False,
            "manifest2": 7,
        }

        controller._save_manifest(interactive=False)

        sa_mock.save_manifest_json.assert_called_with(
            json.dumps({"manifest1": False, "manifest2": 7})
        )

    def test__save_manifest_no_repr(self):
        self_mock = mock.MagicMock()
        self_mock.sa.get_manifest_repr_json.return_value = "{}"
        RemoteController._save_manifest(self_mock, False)

    def test_select_jobs_forced_with_manifest(self):
        self_mock = mock.MagicMock()
        self_mock.launcher.get_value.return_value = True
        self_mock.launcher.manifest = True

        RemoteController.select_jobs(self_mock, [])

        self.assertTrue(self_mock._save_manifest.called)
        self.assertTrue(self_mock.sa.finish_job_selection.called)
        self.assertFalse(self_mock.sa.get_jobs_repr_json.called)

    @mock.patch("checkbox_ng.launcher.controller.CategoryBrowser")
    def test_select_jobs_interactive_modified(self, category_browser_mock):
        self_mock = mock.MagicMock()
        self_mock.launcher.get_value.return_value = False
        all_jobs = ["job1", "job2", "job3"]
        self_mock.sa.get_jobs_repr_json.return_value = json.dumps(all_jobs)
        wanted_set = {"job1", "job3"}
        category_browser_mock.return_value.run.return_value = wanted_set

        RemoteController.select_jobs(self_mock, all_jobs)

        self.assertTrue(category_browser_mock.called)
        self.assertTrue(self_mock.sa.modify_todo_list_json.called)
        self.assertTrue(self_mock._save_manifest.called)
        self.assertTrue(self_mock.sa.finish_job_selection.called)

    @mock.patch("checkbox_ng.launcher.controller.CategoryBrowser")
    def test_select_jobs_interactive_not_modified(self, category_browser_mock):
        self_mock = mock.MagicMock()
        self_mock.launcher.get_value.return_value = False
        all_jobs = ["job1", "job2", "job3"]
        self_mock.sa.get_jobs_repr_json.return_value = json.dumps(all_jobs)
        wanted_set = {"job1", "job2", "job3"}
        category_browser_mock.return_value.run.return_value = wanted_set

        RemoteController.select_jobs(self_mock, all_jobs)

        self.assertTrue(category_browser_mock.called)
        self.assertFalse(self_mock.sa.modify_todo_list_json.called)
        self.assertTrue(self_mock._save_manifest.called)
        self.assertTrue(self_mock.sa.finish_job_selection.called)

    @mock.patch("time.sleep")
    def test_wait_for_job_finishes_on_non_running_state(self, sleep_mock):
        self_mock = mock.MagicMock()
        self_mock.sa.monitor_job.side_effect = [("completed", None)]

        RemoteController.wait_for_job(self_mock, dont_finish=False)

        self.assertTrue(self_mock.finish_job.called)
        self.assertFalse(sleep_mock.called)

    @mock.patch("select.select")
    @mock.patch("time.sleep")
    def test_wait_for_job_sleeps_increasingly(self, sleep_mock, select_mock):
        self_mock = mock.MagicMock()
        select_mock.return_value = ([], [], [])
        self_mock.sa.monitor_job.side_effect = [
            ("running", None),
            ("running", None),
            ("running", None),
            ("running", None),
            ("running", None),
            ("finished", None),
        ]

        RemoteController.wait_for_job(self_mock)

        self.assertTrue(sleep_mock.called)
        calls = sleep_mock.call_args_list
        self.assertEqual(calls[0], mock.call(0))
        self.assertEqual(calls[1], mock.call(0.1))
        self.assertEqual(calls[2], mock.call(0.2))
        self.assertEqual(calls[3], mock.call(0.5))
        self.assertEqual(calls[4], mock.call(0.5))
        self.assertTrue(self_mock.finish_job.called)

    @mock.patch("checkbox_ng.launcher.controller.SimpleUI")
    def test_wait_for_job_with_payload(self, simple_ui_mock):
        self_mock = mock.MagicMock()
        self_mock._is_bootstrapping = False
        payload = "stdout:OK\nstderr:ERROR"
        self_mock.sa.monitor_job.side_effect = [
            ("finished", payload),
        ]

        RemoteController.wait_for_job(self_mock)

        self.assertTrue(self_mock.sa.monitor_job.called)
        self.assertTrue(simple_ui_mock.green_text.called)
        self.assertTrue(simple_ui_mock.red_text.called)
        self.assertTrue(self_mock.finish_job.called)


class IsHostnameALoopbackTests(TestCase):
    @mock.patch("socket.gethostbyname")
    @mock.patch("ipaddress.ip_address")
    def test_is_hostname_a_loopback(self, ip_address_mock, gethostbyname_mock):
        """
        Test that the is_hostname_a_loopback function returns True
        when the ip_address claims it is a loopback
        """
        gethostbyname_mock.return_value = "127.0.0.1"
        # we still can't just use 127.0.0.1 and assume it's a loopback
        # because that address is just a convention and it could be
        # changed by the user, and also this is a thing just for IPv4
        # so we need to mock the ip_address as well
        ip_address_mock.return_value = ip_address_mock
        ip_address_mock.is_loopback = True
        self.assertTrue(is_hostname_a_loopback("foobar"))

    @mock.patch("socket.gethostbyname")
    @mock.patch("ipaddress.ip_address")
    def test_is_hostname_a_loopback_false_case(
        self, ip_address_mock, gethostbyname_mock
    ):
        """
        Test that the is_hostname_a_loopback function returns False
        when the ip_address claims it is not a loopback
        """
        gethostbyname_mock.return_value = "127.0.0.1"
        # we still can't just use 127.0.0.1 and assume it's a loopback
        # because that address is just a convention and it could be
        # changed by the user, and also this is a thing just for IPv4
        # so we need to mock the ip_address as well
        ip_address_mock.return_value = ip_address_mock
        ip_address_mock.is_loopback = False
        self.assertFalse(is_hostname_a_loopback("foobar"))

    @mock.patch("socket.gethostbyname")
    def test_is_hostname_a_loopback_socket_raises(self, gethostbyname_mock):
        """
        Test that the is_hostname_a_loopback function returns False
        when the socket.gethostname function raises an exception
        """
        gethostbyname_mock.side_effect = socket.gaierror
        self.assertFalse(is_hostname_a_loopback("foobar"))
