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

from checkbox_ng.launcher.controller import RemoteController
from checkbox_ng.launcher.controller import is_hostname_a_loopback


class ControllerTests(TestCase):
    @mock.patch("ipaddress.ip_address")
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
        ip_address_mock,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.launcher = "example"
        ctx_mock.args.user = "some username"
        ctx_mock.args.host = "undertest@local"
        ctx_mock.args.port = "9999"

        ip_address_mock.return_value = ip_address_mock
        ip_address_mock.is_loopback = False

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
    def test_is_hostname_a_loopback_socket_raises(self, gethostbyname_mock):
        """
        Test that the is_hostname_a_loopback function returns False
        when the socket.gethostname function raises an exception
        """
        gethostbyname_mock.side_effect = socket.gaierror
        self.assertFalse(is_hostname_a_loopback("foobar"))
