# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

import json
from os.path import exists
from functools import partial

from unittest import TestCase, mock

from checkbox_ng.config import load_configs
from checkbox_ng.launcher.agent import SessionAssistantAgent

from plainbox.abc import IJobResult
from plainbox.impl.config import Configuration
from plainbox.impl.result import MemoryJobResult

from plainbox.impl.secure.sudo_broker import is_passwordless_sudo

from plainbox.impl.session.remote_assistant import (
    RemoteSessionAssistant,
    RemoteSessionStates,
    allowed_when,
)
from plainbox.impl.session.assistant import SessionAssistant


class RemoteAssistantTests(TestCase):
    def test_allowed_when_ok(self):
        self_mock = mock.MagicMock()

        @allowed_when(RemoteSessionStates.Idle)
        def allowed(self, *args): ...

        self_mock.state = RemoteSessionStates.Idle
        allowed(self_mock)

    def test_allowed_when_fail(self):
        self_mock = mock.MagicMock()

        @allowed_when(RemoteSessionStates.Idle)
        def not_allowed(self, *args): ...

        self_mock.state = RemoteSessionStates.Started
        with self.assertRaises(RuntimeError):
            not_allowed(self_mock)

    @mock.patch.object(SessionAssistant, "__init__")
    @mock.patch("plainbox.impl.session.remote_assistant.is_passwordless_sudo")
    def test__reset_sa(self, is_passwordless_sudo_mock, init_mock):
        init_mock.return_value = None
        # RSA constructor calls _reset_sa, which in turns creates a new SA
        rsa = RemoteSessionAssistant(lambda: None)
        self.assertEqual(init_mock.call_count, 1)

    @mock.patch("plainbox.impl.session.remote_assistant.guess_normal_user")
    @mock.patch("fnmatch.filter")
    def test_start_session_with_launcher(self, mock_filter, mock_gnu):
        # the real tp is referenced later on by it's second field
        mock_filter.return_value = [("tp", "tp")]
        mock_gnu.return_value = "user"
        extra_cfg = dict()
        extra_cfg["launcher"] = "test_launcher"
        rsa = mock.Mock()
        rsa.get_test_plans.return_value = [mock.Mock()]
        rsa.state = RemoteSessionStates.Idle

        def get_test_plan_mock(name):
            to_r = mock.Mock()
            to_r.name = name
            return to_r

        rsa._sa.get_test_plan.side_effect = get_test_plan_mock
        rsa.start_session = partial(RemoteSessionAssistant.start_session, rsa)
        with mock.patch("plainbox.impl.config.Configuration.from_text") as cm:
            cm.return_value = Configuration()
            tps = RemoteSessionAssistant.start_session_json(
                rsa, json.dumps(extra_cfg)
            )
            tps = json.loads(tps)
            self.assertEqual(tps[0][0][1], "tp")

    @mock.patch("plainbox.impl.session.remote_assistant.guess_normal_user")
    @mock.patch("fnmatch.filter")
    def test_start_session_without_launcher(self, mock_filter, mock_gnu):
        # the real tp is referenced later on by it's second field
        mock_filter.return_value = [("tp", "tp")]
        mock_gnu.return_value = "user"
        extra_cfg = dict()
        extra_cfg["launcher"] = "test_launcher"
        rsa = mock.Mock()
        rsa.get_test_plans.return_value = [mock.Mock()]
        rsa.state = RemoteSessionStates.Idle
        with mock.patch("plainbox.impl.config.Configuration.from_text") as cm:
            cm.return_value = Configuration()
            tps = RemoteSessionAssistant.start_session(rsa, extra_cfg)
            self.assertEqual(tps[0][0][1], "tp")

    def test_resume_by_id_with_session_id(self):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.state = RemoteSessionStates.Idle
        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        RemoteSessionAssistant.resume_by_id(rsa, "session_id")
        self.assertEqual(rsa.state, RemoteSessionStates.TestsSelected)

    def test_resume_by_id_bad_session_id(self):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.state = RemoteSessionStates.Idle
        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        RemoteSessionAssistant.resume_by_id(rsa, "bad_id")
        self.assertEqual(rsa.state, RemoteSessionStates.Idle)

    def test_resume_by_id_without_session_id(self):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.state = RemoteSessionStates.Idle
        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        RemoteSessionAssistant.resume_by_id(rsa)
        self.assertEqual(rsa.state, RemoteSessionStates.TestsSelected)

    @mock.patch("plainbox.impl.session.remote_assistant.load_configs")
    def test_resume_by_id_with_result_file_ok(self, mock_load_configs):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.get_rerun_candidates.return_value = []
        rsa.state = RemoteSessionStates.Idle

        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        os_path_exists_mock = mock.Mock()

        with mock.patch("plainbox.impl.session.remote_assistant._") as mock__:
            mock__.side_effect = lambda x: x
            with mock.patch("os.path.exists", os_path_exists_mock):
                with mock.patch(
                    "builtins.open",
                    mock.mock_open(
                        read_data="""{
                        "outcome" : "pass",
                        "comments" : "Outcome loaded from file"
                        }"""
                    ),
                ):
                    os_path_exists_mock.return_value = True
                    RemoteSessionAssistant.resume_by_id(rsa)

        mjr = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "comments": "Outcome loaded from file",
            }
        )
        rsa._sa.use_job_result.assert_called_with(rsa._last_job, mjr, True)

    @mock.patch("plainbox.impl.session.remote_assistant.load_configs")
    def test_resume_by_id_with_result_file_garbage_outcome(
        self, mock_load_configs
    ):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.get_rerun_candidates.return_value = []
        rsa.state = RemoteSessionStates.Idle

        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        os_path_exists_mock = mock.Mock()

        with mock.patch("plainbox.impl.session.remote_assistant._") as mock__:
            mock__.side_effect = lambda x: x
            with mock.patch("os.path.exists", os_path_exists_mock):
                with mock.patch(
                    "builtins.open",
                    mock.mock_open(
                        read_data="""{
                        "outcome" : "unknown_value_for_outcome",
                        "comments" : "Outcome loaded from file"
                        }"""
                    ),
                ):
                    os_path_exists_mock.return_value = True
                    RemoteSessionAssistant.resume_by_id(rsa)

        mjr = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "comments": "Outcome loaded from file",
            }
        )
        rsa._sa.use_job_result.assert_called_with(rsa._last_job, mjr, True)

    @mock.patch("plainbox.impl.session.remote_assistant.load_configs")
    def test_resume_by_id_with_result_no_file_noreturn(
        self, mock_load_configs
    ):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.get_rerun_candidates.return_value = []
        rsa.state = RemoteSessionStates.Idle
        job_state = rsa._sa.get_job_state.return_value
        job_state.result.outcome = None

        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        os_path_exists_mock = mock.Mock()

        rsa._sa.get_job.return_value.plugin = "shell"

        with mock.patch("os.path.exists", os_path_exists_mock):
            os_path_exists_mock.return_value = False
            rsa._sa.get_job.return_value.get_flag_set.return_value = {
                "noreturn"
            }

            RemoteSessionAssistant.resume_by_id(rsa)

        mjr = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "comments": (
                    "Job rebooted the machine or the Checkbox agent. "
                    "Resuming the session and marking it as passed "
                    "because the job has the `noreturn` flag"
                ),
            }
        )

        rsa._sa.use_job_result.assert_called_with(rsa._last_job, mjr, True)

    @mock.patch("plainbox.impl.session.remote_assistant.load_configs")
    def test_resume_by_id_with_result_no_file_normal(self, mock_load_configs):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.get_rerun_candidates.return_value = []
        rsa.state = RemoteSessionStates.Idle
        job_state = rsa._sa.get_job_state.return_value
        job_state.result.outcome = None

        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        os_path_exists_mock = mock.Mock()

        rsa._sa.get_job.return_value.plugin = "shell"

        with mock.patch("os.path.exists", os_path_exists_mock):
            os_path_exists_mock.return_value = False
            rsa._sa.get_job.return_value.get_flag_set.return_value = {}

            RemoteSessionAssistant.resume_by_id(rsa)

        mjr = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_CRASH,
                "comments": (
                    "Job rebooted the machine or the Checkbox agent. "
                    "Resuming the session and marking it as crashed."
                ),
            }
        )

        rsa._sa.use_job_result.assert_called_with(rsa._last_job, mjr, True)

    @mock.patch("plainbox.impl.session.remote_assistant.load_configs")
    def test_resume_by_id_with_result_no_file_already_set(
        self, mock_load_configs
    ):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.get_rerun_candidates.return_value = []
        rsa.state = RemoteSessionStates.Idle
        job_state = rsa._sa.get_job_state.return_value
        job_state.result.outcome = IJobResult.OUTCOME_PASS
        job_state.result.comments = None

        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        os_path_exists_mock = mock.Mock()

        rsa._sa.get_job.return_value.plugin = "shell"

        with mock.patch("os.path.exists", os_path_exists_mock):
            os_path_exists_mock.return_value = False
            rsa._sa.get_job.return_value.get_flag_set.return_value = {}

            RemoteSessionAssistant.resume_by_id(rsa)

        mjr = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "comments": "",
            }
        )

        rsa._sa.use_job_result.assert_called_with(rsa._last_job, mjr, True)

    @mock.patch("plainbox.impl.session.remote_assistant.load_configs")
    def test_resume_by_id_with_result_file_not_json(self, mock_load_configs):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa.get_rerun_candidates.return_value = []
        rsa.state = RemoteSessionStates.Idle
        job_state = rsa._sa.get_job_state.return_value
        job_state.result.outcome = None

        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa.prepare_resume_session.return_value = mock_meta
        os_path_exists_mock = mock.Mock()
        with mock.patch("plainbox.impl.session.remote_assistant._") as mock__:
            mock__.side_effect = lambda x: x
            with mock.patch("builtins.open", mock.mock_open(read_data="!@!")):
                with mock.patch("os.path.exists", os_path_exists_mock):
                    os_path_exists_mock.return_value = True
                    RemoteSessionAssistant.resume_by_id(rsa)

        mjr = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "comments": "Automatically passed after resuming execution",
            }
        )

        rsa._sa.use_job_result.assert_called_with(rsa._last_job, mjr, True)

    def test_remember_users_response_quit(self):
        self_mock = mock.MagicMock()
        self_mock.state = RemoteSessionStates.Interacting

        RemoteSessionAssistant.remember_users_response(self_mock, "quit")

        self.assertTrue(self_mock.abandon_session.called)

    def test_remember_users_response_rollback(self):
        self_mock = mock.MagicMock()
        self_mock.state = RemoteSessionStates.Interacting

        RemoteSessionAssistant.remember_users_response(self_mock, "rollback")

        self.assertEqual(self_mock.state, RemoteSessionStates.TestsSelected)

    def test_remember_users_response_run(self):
        self_mock = mock.MagicMock()
        self_mock.state = RemoteSessionStates.Interacting

        RemoteSessionAssistant.remember_users_response(self_mock, "run")

        self.assertEqual(self_mock.state, RemoteSessionStates.Running)

    def test_note_metadata_starting_job(self):
        self_mock = mock.MagicMock()
        note_metadata_starting_job = partial(
            RemoteSessionAssistant.note_metadata_starting_job,
            self_mock,
        )
        self_mock.note_metadata_starting_job = note_metadata_starting_job
        RemoteSessionAssistant.note_metadata_starting_job_json(
            self_mock, "{}", mock.MagicMock()
        )
        self.assertTrue(self_mock._sa.note_metadata_starting_job.called)

    def test_abandon_session(self):
        self_mock = mock.MagicMock()
        RemoteSessionAssistant.abandon_session(self_mock)
        self.assertTrue(self_mock._reset_sa.called)

    def test_delete_sessions(self):
        self_mock = mock.MagicMock()
        RemoteSessionAssistant.delete_sessions(self_mock, [])
        self.assertTrue(self_mock._sa.delete_sessions.called)

    def test_get_resumable_sessions(self):
        self_mock = mock.MagicMock()
        RemoteSessionAssistant.get_resumable_sessions(self_mock)
        self.assertTrue(self_mock._sa.get_resumable_sessions.called)

    def test_configuration_type(self):
        # This is used to allow the controller to create netref configurations.
        conf_type = RemoteSessionAssistant.configuration_type(mock.MagicMock())
        self.assertEqual(conf_type, Configuration)

    def test_start_bootstrap_json(self):
        self_mock = mock.MagicMock()
        self_mock.state = RemoteSessionStates.Started
        self_mock.start_bootstrap = partial(
            RemoteSessionAssistant.start_bootstrap, self_mock
        )
        self_mock._sa.start_bootstrap.return_value = [
            "job1",
            "job2",
        ]

        job_list_str = RemoteSessionAssistant.start_bootstrap_json(self_mock)

        self.assertTrue(self_mock._sa.start_bootstrap.called)
        self.assertEqual(["job1", "job2"], json.loads(job_list_str))

    def test_finish_bootstrap_json(self):
        self_mock = mock.MagicMock()
        self_mock.finish_bootstrap = partial(
            RemoteSessionAssistant.finish_bootstrap, self_mock
        )
        self_mock._sa.get_static_todo_list.return_value = static_todo_list = [
            "test_{}".format(x) for x in range(10)
        ]
        to_r = {x: mock.MagicMock() for x in static_todo_list}

        def get_job_state(id):
            return to_r[id]

        self_mock._sa.get_job_state = get_job_state

        def get_value(top, key):
            assert top == "ui"
            if key == "auto_retry":
                return True
            elif key == "max_attempts":
                return 10
            assert False, "Undefined key"

        self_mock._launcher.get_value = get_value

        bootstrapped_todo = json.loads(
            RemoteSessionAssistant.finish_bootstrap_json(self_mock)
        )

        self.assertEqual(self_mock.state, RemoteSessionStates.Bootstrapped)
        self.assertEqual(bootstrapped_todo, static_todo_list)
        self.assertTrue(
            all(
                to_r[x].attempts == get_value("ui", "max_attempts")
                for x in bootstrapped_todo
            )
        )

    def test_get_manifest_repr_json(self):
        self_mock = mock.MagicMock()
        self_mock.get_manifest_repr = partial(
            RemoteSessionAssistant.get_manifest_repr, self_mock
        )
        self_mock._sa.get_manifest_repr.return_value = {"manifest1": True}

        manifest = RemoteSessionAssistant.get_manifest_repr_json(self_mock)

        self.assertEqual(json.loads(manifest), {"manifest1": True})

    def test_modify_todo_list_json(self):
        self_mock = mock.MagicMock()
        self_mock.modify_todo_list = partial(
            RemoteSessionAssistant.modify_todo_list, self_mock
        )
        chosen_jobs_list = ["job1", "job2", "job3"]
        chosen_jobs_json = json.dumps(chosen_jobs_list)

        RemoteSessionAssistant.modify_todo_list_json(
            self_mock, chosen_jobs_json
        )

        self.assertTrue(self_mock._sa.use_alternate_selection.called)

    def test_finish_job_json_with_result(self):
        self_mock = mock.MagicMock()
        mock_result_obj = mock.MagicMock()
        mock_result_obj.tr_outcome.return_value = "PASS"
        mock_result_obj.outcome_color_ansi.return_value = "[green]PASS[/green]"
        self_mock.finish_job.return_value = mock_result_obj

        input_result_data = {
            "outcome": "PASS",
            "comments": "Completed successfully",
        }
        input_result_json = json.dumps(input_result_data)

        response_json = RemoteSessionAssistant.finish_job_json(
            self_mock, input_result_json
        )

        self_mock.finish_job.assert_called_once_with(input_result_data)
        expected_response = {
            "tr_outcome": "PASS",
            "outcome_color": "[green]PASS[/green]",
        }
        self.assertEqual(json.loads(response_json), expected_response)

    def test_finish_job_json_without_result(self):
        self_mock = mock.MagicMock()
        mock_result_obj = mock.MagicMock()
        mock_result_obj.tr_outcome.return_value = "FAIL"
        mock_result_obj.outcome_color_ansi.return_value = "[red]FAIL[/red]"
        self_mock.finish_job.return_value = mock_result_obj

        response_json = RemoteSessionAssistant.finish_job_json(self_mock)

        self_mock.finish_job.assert_called_once_with(None)
        expected_response = {
            "tr_outcome": "FAIL",
            "outcome_color": "[red]FAIL[/red]",
        }
        self.assertEqual(json.loads(response_json), expected_response)

    def test_finish_job_json_handles_none_result_from_finish_job(self):
        self_mock = mock.MagicMock()
        self_mock.finish_job.return_value = None

        response = RemoteSessionAssistant.finish_job_json(self_mock)

        self_mock.finish_job.assert_called_once_with(None)
        self.assertIsNone(response)

    def test_has_any_job_failed_is_true_if_a_job_failed(self):
        self_mock = mock.MagicMock()

        passing_job = mock.MagicMock()
        passing_job.result.outcome = IJobResult.OUTCOME_PASS

        failing_job = mock.MagicMock()
        failing_job.result.outcome = IJobResult.OUTCOME_FAIL

        self_mock.manager.default_device_context._state._job_state_map = {
            "job1": passing_job,
            "job2": failing_job,
        }

        self.assertTrue(RemoteSessionAssistant.has_any_job_failed(self_mock))

    def test_has_any_job_failed_is_true_if_a_job_crashed(self):
        self_mock = mock.MagicMock()

        passing_job = mock.MagicMock()
        passing_job.result.outcome = IJobResult.OUTCOME_PASS

        crashing_job = mock.MagicMock()
        crashing_job.result.outcome = IJobResult.OUTCOME_CRASH

        self_mock.manager.default_device_context._state._job_state_map = {
            "job1": passing_job,
            "job2": crashing_job,
        }

        self.assertTrue(RemoteSessionAssistant.has_any_job_failed(self_mock))

    def test_has_any_job_failed_is_false_if_no_jobs_failed(self):
        self_mock = mock.MagicMock()

        passing_job_1 = mock.MagicMock()
        passing_job_1.result.outcome = IJobResult.OUTCOME_PASS

        passing_job_2 = mock.MagicMock()
        passing_job_2.result.outcome = IJobResult.OUTCOME_PASS

        self_mock.manager.default_device_context._state._job_state_map = {
            "job1": passing_job_1,
            "job2": passing_job_2,
        }

        self.assertFalse(RemoteSessionAssistant.has_any_job_failed(self_mock))

    def test_has_any_job_failed_is_false_for_empty_job_map(self):
        self_mock = mock.MagicMock()
        self_mock.manager.default_device_context._state._job_state_map = {}
        self.assertFalse(RemoteSessionAssistant.has_any_job_failed(self_mock))


class RemoteAssistantFinishJobTests(TestCase):
    def setUp(self):
        self.rsa = mock.MagicMock()
        self.rsa._be = None

    @mock.patch("plainbox.impl.session.remote_assistant.JobResultBuilder")
    def test_no_result_after_auto_resume(self, MockJobResultBuilder):
        self.rsa._currently_running_job = "job_id"
        mock_job = mock.Mock()
        mock_job.plugin = "shell"
        mock_builder = MockJobResultBuilder.return_value
        mock_builder.get_result.return_value = IJobResult.OUTCOME_PASS

        result = RemoteSessionAssistant.finish_job(self.rsa)

        self.rsa._sa.use_job_result.assert_called_with("job_id", "pass")
        self.assertEqual(result, IJobResult.OUTCOME_PASS)
        MockJobResultBuilder.assert_called_with(
            outcome=IJobResult.OUTCOME_PASS,
            comments="Automatically passed while resuming",
        )

    def test_no_result_with_be(self):
        self.rsa._currently_running_job = "job_id"
        self.rsa._be = mock.Mock()
        wait_res = mock.Mock()
        self.rsa._be.wait.return_value = wait_res
        wait_get_result_res = mock.Mock()
        self.rsa._be.wait().get_result = wait_get_result_res
        wait_get_result_res.return_value = IJobResult.OUTCOME_PASS

        result = RemoteSessionAssistant.finish_job(self.rsa)

        self.assertTrue(self.rsa._be.wait.called)
        self.assertTrue(self.rsa._be.wait().get_result)
        self.assertEqual(result, IJobResult.OUTCOME_PASS)

    @mock.patch("plainbox.impl.session.remote_assistant.JobResultBuilder")
    def test_no_result_with_be_but_no_builder(self, MockJobResultBuilder):
        self.rsa._currently_running_job = "job_id"
        mock_job = mock.Mock()
        mock_job.plugin = "shell"
        self.rsa._be = mock.Mock()
        self.rsa._be.wait.return_value = None
        mock_builder = MockJobResultBuilder.return_value
        mock_builder.get_result.return_value = IJobResult.OUTCOME_PASS

        result = RemoteSessionAssistant.finish_job(self.rsa)

        self.rsa._sa.use_job_result.assert_called_with("job_id", "pass")
        self.assertEqual(result, IJobResult.OUTCOME_PASS)
        MockJobResultBuilder.assert_called_with(
            outcome=IJobResult.OUTCOME_PASS,
            comments="Automatically passed while resuming",
        )


class SessionAssistantAgentTests(TestCase):
    def test_on_connect(self):
        conn = mock.Mock()
        conn._config = {"endpoints": [("first", 1), ("second", 2)]}
        blaster_mock = mock.Mock()
        SessionAssistantAgent.controller_blaster = blaster_mock
        SessionAssistantAgent.controlling_controller_conn = mock.Mock()
        saa = mock.Mock()
        SessionAssistantAgent.on_connect(saa, conn)
        blaster_mock.assert_called_with(
            "Forcefully disconnected by new controller from second:2"
        )
