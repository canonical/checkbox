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

from unittest import TestCase, mock

from plainbox.abc import IJobResult
from plainbox.impl.config import Configuration

from plainbox.impl.secure.sudo_broker import is_passwordless_sudo

from plainbox.impl.session import remote_assistant
from plainbox.impl.session.assistant import SessionAssistant


class RemoteAssistantTests(TestCase):
    def test_allowed_when_ok(self):
        self_mock = mock.MagicMock()
        allowed_when = remote_assistant.RemoteSessionAssistant.allowed_when

        @allowed_when(remote_assistant.Idle)
        def allowed(self, *args):
            ...

        self_mock._state = remote_assistant.Idle
        allowed(self_mock)

    def test_allowed_when_fail(self):
        self_mock = mock.MagicMock()
        allowed_when = remote_assistant.RemoteSessionAssistant.allowed_when

        @allowed_when(remote_assistant.Idle)
        def not_allowed(self, *args):
            ...

        self_mock._state = remote_assistant.Started
        with self.assertRaises(AssertionError):
            not_allowed(self_mock)

    @mock.patch("plainbox.impl.secure.sudo_broker.is_passwordless_sudo")
    def test__reset_sa(self, is_passwordless_sudo_mock):
        with mock.patch.object(SessionAssistant, "__init__") as init_mock:
            init_mock.return_value = None
            # RSA constructor calls _reset_sa, which in turns creates a new SA
            rsa = remote_assistant.RemoteSessionAssistant(lambda: None)
            init_mock.assert_called_once()

    @mock.patch("fnmatch.filter")
    def test_start_session_with_launcher(self, mock_filter):
        # the real tp is referenced later on by it's second field
        mock_filter.return_value = [("tp", "tp")]
        extra_cfg = dict()
        extra_cfg["launcher"] = "test_launcher"
        rsa = mock.Mock()
        rsa._sa.get_test_plans.return_value = [mock.Mock()]
        rsa._state = remote_assistant.Idle
        with mock.patch("plainbox.impl.config.Configuration.from_text") as cm:
            cm.return_value = Configuration()
            tps = remote_assistant.RemoteSessionAssistant.start_session(
                rsa, extra_cfg
            )
            self.assertEqual(tps[0][0][1], "tp")

    @mock.patch("fnmatch.filter")
    def test_start_session_without_launcher(self, mock_filter):
        # the real tp is referenced later on by it's second field
        mock_filter.return_value = [("tp", "tp")]
        extra_cfg = dict()
        extra_cfg["launcher"] = "test_launcher"
        rsa = mock.Mock()
        rsa._sa.get_test_plans.return_value = [mock.Mock()]
        rsa._state = remote_assistant.Idle
        with mock.patch("plainbox.impl.config.Configuration.from_text") as cm:
            cm.return_value = Configuration()
            tps = remote_assistant.RemoteSessionAssistant.start_session(
                rsa, extra_cfg
            )
            self.assertEqual(tps[0][0][1], "tp")

    def test_resume_by_id_with_session_id(self):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa._state = remote_assistant.Idle
        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa._sa.resume_session.return_value = mock_meta
        remote_assistant.RemoteSessionAssistant.resume_by_id(rsa, "session_id")
        self.assertEqual(rsa._state, "testsselected")

    def test_resume_by_id_bad_session_id(self):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa._state = remote_assistant.Idle
        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa._sa.resume_session.return_value = mock_meta
        remote_assistant.RemoteSessionAssistant.resume_by_id(rsa, "bad_id")
        self.assertEqual(rsa._state, "idle")

    def test_resume_by_id_without_session_id(self):
        rsa = mock.Mock()
        resumable_session = mock.Mock()
        resumable_session.id = "session_id"
        rsa._sa.get_resumable_sessions.return_value = [resumable_session]
        rsa._state = remote_assistant.Idle
        mock_meta = mock.Mock()
        mock_meta.app_blob = b'{"launcher": "", "testplan_id": "tp_id"}'

        rsa._sa.resume_session.return_value = mock_meta
        remote_assistant.RemoteSessionAssistant.resume_by_id(rsa)
        self.assertEqual(rsa._state, "testsselected")


class RemoteAssistantFinishJobTests(TestCase):
    def setUp(self):
        self.rsa = mock.MagicMock()
        self.rsa._sa = mock.Mock()
        self.rsa._be = None

    @mock.patch("plainbox.impl.session.remote_assistant.JobResultBuilder")
    def test_no_result_after_auto_resume(self, MockJobResultBuilder):
        self.rsa._currently_running_job = "job_id"
        mock_job = mock.Mock()
        mock_job.plugin = "shell"
        mock_builder = MockJobResultBuilder.return_value
        mock_builder.get_result.return_value = IJobResult.OUTCOME_PASS

        result = remote_assistant.RemoteSessionAssistant.finish_job(self.rsa)

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

        result = remote_assistant.RemoteSessionAssistant.finish_job(self.rsa)

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

        result = remote_assistant.RemoteSessionAssistant.finish_job(self.rsa)

        self.rsa._sa.use_job_result.assert_called_with("job_id", "pass")
        self.assertEqual(result, IJobResult.OUTCOME_PASS)
        MockJobResultBuilder.assert_called_with(
            outcome=IJobResult.OUTCOME_PASS,
            comments="Automatically passed while resuming",
        )
