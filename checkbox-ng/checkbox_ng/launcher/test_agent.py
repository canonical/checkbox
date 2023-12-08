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

import json
from unittest import TestCase, mock

from checkbox_ng.launcher.agent import is_the_session_noninteractive
from checkbox_ng.launcher.agent import exit_if_port_unavailable
from checkbox_ng.launcher.agent import RemoteAgent
from plainbox.impl.session.assistant import ResumeCandidate
from plainbox.impl.session.state import SessionMetaData


@mock.patch("checkbox_ng.launcher.agent._")
@mock.patch("checkbox_ng.launcher.agent._logger")
@mock.patch("checkbox_ng.launcher.agent.is_passwordless_sudo")
@mock.patch("checkbox_ng.launcher.agent.SessionAssistantAgent")
@mock.patch("checkbox_ng.launcher.agent.RemoteDebRestartStrategy")
@mock.patch("checkbox_ng.launcher.agent.RemoteSessionAssistant")
@mock.patch("checkbox_ng.launcher.agent.ThreadedServer")
@mock.patch("os.geteuid")
@mock.patch("os.getenv")
class AgentTests(TestCase):
    # used to load an empty launcher with no error
    def test_invoked_ok(
        self,
        getenv_mock,
        geteuid_mock,
        threaded_server_mock,
        remote_assistant_mock,
        remote_strategy_mock,
        session_assistant_mock,
        pwdless_sudo_mock,
        logger_mock,
        gettext_mock,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.resume = False

        self_mock = mock.MagicMock()

        geteuid_mock.return_value = 0  # agent will not run as non-root
        pwdless_sudo_mock.return_value = True  # agent needs pwd-less sudo
        getenv_mock.return_value = None

        with mock.patch("builtins.open"):
            RemoteAgent.invoked(self_mock, ctx_mock)

        # agent server was created
        self.assertTrue(threaded_server_mock.called)
        server = threaded_server_mock.return_value
        # the server was started
        self.assertTrue(server.start.called)

    # used to load an empty launcher with no error
    def test_invoked_with_resume_warns(
        self,
        getenv_mock,
        geteuid_mock,
        threaded_server_mock,
        remote_assistant_mock,
        remote_strategy_mock,
        session_assistant_mock,
        pwdless_sudo_mock,
        logger_mock,
        gettext_mock,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.resume = True

        self_mock = mock.MagicMock()

        geteuid_mock.return_value = 0  # agent will not run as non-root
        pwdless_sudo_mock.return_value = True  # agent needs pwd-less sudo
        getenv_mock.return_value = None

        with mock.patch("builtins.open"):
            RemoteAgent.invoked(self_mock, ctx_mock)

        # agent server was created
        self.assertTrue(threaded_server_mock.called)
        server = threaded_server_mock.return_value
        # the server was started
        self.assertTrue(server.start.called)
        logger_mock.warning.assert_called()

    def test_invoked_with_session(
        self,
        getenv_mock,
        geteuid_mock,
        threaded_server_mock,
        remote_assistant_mock,
        remote_strategy_mock,
        sa_mock,
        pwdless_sudo_mock,
        logger_mock,
        gettext_mock,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.resume = False

        self_mock = mock.MagicMock()

        geteuid_mock.return_value = 0

        ctx_mock.sa.get_resumable_sessions.return_value = [
            ResumeCandidate("an_id", SessionMetaData())
        ]
        with mock.patch(
            "checkbox_ng.launcher.agent.is_the_session_noninteractive"
        ) as itni:
            itni.return_value = True

            RemoteAgent.invoked(self_mock, ctx_mock)
            remote_assistant_mock.return_value.resume_by_id.assert_called()

        remote_assistant_mock.reset_mock()

        with mock.patch(
            "checkbox_ng.launcher.agent.is_the_session_noninteractive"
        ) as itni:
            itni.return_value = False

            RemoteAgent.invoked(self_mock, ctx_mock)
            self.assertFalse(
                remote_assistant_mock.return_value.resume_by_id.called
            )


class IsTheSessionNonInteractiveTests(TestCase):
    def test_a_non_interactive_one(self):
        a_non_interactive_launcher = """
            [ui]
            type = silent
        """
        app_blob = json.dumps({"launcher": a_non_interactive_launcher})
        metadata = SessionMetaData(app_blob=app_blob.encode("utf-8"))

        candidate = ResumeCandidate("an_id", metadata)
        self.assertTrue(is_the_session_noninteractive(candidate))

    def test_an_interactive(self):
        a_non_interactive_launcher = ""  # the defautl one is interactive
        app_blob = json.dumps({"launcher": a_non_interactive_launcher})
        metadata = SessionMetaData(app_blob=app_blob.encode("utf-8"))

        candidate = ResumeCandidate("an_id", metadata)
        self.assertFalse(is_the_session_noninteractive(candidate))


class ExitIfPortUnavilableTests(TestCase):
    def test_exit_if_port_unavailable_it_is(self):
        mocked_socket = mock.Mock()
        mocked_socket.connect_ex.return_value = 1
        with mock.patch("socket.socket") as socket_mock:
            socket_mock.return_value = mocked_socket
            self.assertIsNone(exit_if_port_unavailable(1234))

    def test_exit_if_port_unavailable_nope(self):
        mocked_socket = mock.Mock()
        mocked_socket.connect_ex.return_value = 0
        with mock.patch("socket.socket") as socket_mock:
            socket_mock.return_value = mocked_socket
            with self.assertRaises(SystemExit):
                exit_if_port_unavailable(1234)


class RegisterArgumentsTests(TestCase):
    def test_register_arguments(self):
        parser = mock.Mock()
        rsa = mock.Mock()
        with mock.patch("checkbox_ng.launcher.agent._") as _mock:
            _mock.return_value = "_"
            RemoteAgent.register_arguments(rsa, parser)
            parser.add_argument.assert_any_call(
                "--resume", action="store_true", help="_"
            )
            parser.add_argument.assert_any_call(
                "--port", type=int, default=18871, help="_"
            )
