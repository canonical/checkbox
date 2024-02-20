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

from unittest import TestCase, mock

from checkbox_ng.urwid_ui import ResumeInstead
from checkbox_ng.launcher.controller import RemoteController
from checkbox_ng.launcher.controller import is_hostname_a_loopback


class ControllerTests(TestCase):
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

        mock_job_state_map = {
            "job1": mock.MagicMock(result=mock.MagicMock(outcome="pass")),
            "job2": mock.MagicMock(result=mock.MagicMock(outcome="pass")),
        }
        self_mock._sa.manager.default_device_context._state._job_state_map = (
            mock_job_state_map
        )
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
        self_mock._sa.manager.default_device_context._state._job_state_map = (
            mock_job_state_map
        )
        RemoteController.finish_session(self_mock)

        self.assertTrue(self_mock._has_anything_failed)

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
        self_mock._sa.manager.default_device_context._state._job_state_map = (
            mock_job_state_map
        )
        RemoteController.finish_session(self_mock)

        self.assertTrue(self_mock._has_anything_failed)

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
        self_mock.sa.sideloaded_providers = True  # trigger the warning
        # the session is not interactive
        self_mock.launcher.get_value.return_value = False

        RemoteController.resume_or_start_new_session(self_mock)

        self.assertTrue(self_mock.interactively_choose_tp.called)

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
        sa_mock._sa.resume_session.return_value = metadata_mock
        sa_mock._sa.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="non-blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock._sa.resume_session.assert_called_once_with("123")
        sa_mock._sa.select_test_plan.assert_called_once_with("abc")
        self.assertTrue(sa_mock._sa.bootstrap.called)
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
        sa_mock._sa.resume_session.return_value = metadata_mock
        sa_mock._sa.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="non-blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock._sa.resume_session.assert_called_once_with("123")
        sa_mock._sa.select_test_plan.assert_called_once_with("abc")
        self.assertTrue(sa_mock._sa.bootstrap.called)
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
        sa_mock._sa.resume_session.return_value = metadata_mock
        sa_mock._sa.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock._sa.resume_session.assert_called_once_with("123")
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
        sa_mock._sa.resume_session.return_value = metadata_mock
        sa_mock._sa.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="non-blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock._sa.resume_session.assert_called_once_with("123")
        sa_mock._sa.select_test_plan.assert_called_once_with("abc")
        self.assertTrue(sa_mock._sa.bootstrap.called)
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
        sa_mock._sa.resume_session.return_value = metadata_mock
        sa_mock._sa.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock._sa.resume_session.assert_called_once_with("123")
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
        sa_mock._sa.resume_session.return_value = metadata_mock
        sa_mock._sa.get_job_state.return_value = mock.MagicMock(
            effective_certification_status="blocker"
        )

        self_mock = mock.MagicMock(sa=sa_mock)

        RemoteController._resume_session(self_mock, resume_params)

        # Assertions
        sa_mock._sa.resume_session.assert_called_once_with("123")
        sa_mock.resume_by_id.assert_called_once_with(
            "123",
            {
                "comments": None,
                "outcome": None,
            },
        )

    def test_interactively_choose_tp(self):
        self_mock = mock.MagicMock()

        # by default always try to start a new session and not resuming
        RemoteController.interactively_choose_tp(self_mock, [])

        self.assertTrue(self_mock._new_session_flow.called)
        self.assertFalse(self_mock._resume_session_menu.called)

    def test_interactively_choose_tp_resume(self):
        self_mock = mock.MagicMock()
        self_mock._new_session_flow.side_effect = ResumeInstead
        self_mock._resume_session_menu.return_value = True

        RemoteController.interactively_choose_tp(self_mock, [])

        self.assertTrue(self_mock._new_session_flow.called)
        self.assertTrue(self_mock._resume_session_menu.called)

    def test_interactively_choose_tp_resume_retry_tp(self):
        self_mock = mock.MagicMock()
        self_mock._new_session_flow.side_effect = [ResumeInstead, True]
        self_mock._resume_session_menu.return_value = True

        RemoteController.interactively_choose_tp(self_mock, [])

        self.assertTrue(self_mock._new_session_flow.called)
        self.assertTrue(self_mock._resume_session_menu.called)

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
