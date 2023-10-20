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
from plainbox.impl.session import remote_assistant


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


class RemoteAssistantFinishJobTests(TestCase):
    def setUp(self):
        self.rsa = remote_assistant.RemoteSessionAssistant("")
        self.rsa._sa = mock.Mock()
        self.rsa._be = None

    @mock.patch("plainbox.impl.session.remote_assistant.JobResultBuilder")
    def test_no_result_after_auto_resume(self, MockJobResultBuilder):
        self.rsa._currently_running_job = "job_id"
        mock_job = mock.Mock()
        mock_job.plugin = "shell"
        mock_builder = MockJobResultBuilder.return_value
        mock_builder.get_result.return_value = IJobResult.OUTCOME_PASS

        result = self.rsa.finish_job()

        self.rsa._sa.use_job_result.assert_called_with("job_id", "pass")
        self.assertEqual(result, IJobResult.OUTCOME_PASS)
        MockJobResultBuilder.assert_called_with(
            outcome=IJobResult.OUTCOME_PASS,
            comments="Automatically passed while resuming",
        )
