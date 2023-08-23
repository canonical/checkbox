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

from checkbox_ng.launcher.slave import RemoteSlave


class SlaveTests(TestCase):
    @mock.patch("checkbox_ng.launcher.slave._")
    @mock.patch("checkbox_ng.launcher.slave._logger")
    @mock.patch("checkbox_ng.launcher.slave.is_passwordless_sudo")
    @mock.patch("checkbox_ng.launcher.slave.SessionAssistantSlave")
    @mock.patch("checkbox_ng.launcher.slave.RemoteDebRestartStrategy")
    @mock.patch("checkbox_ng.launcher.slave.RemoteSessionAssistant")
    @mock.patch("checkbox_ng.launcher.slave.ThreadedServer")
    @mock.patch("os.geteuid")
    @mock.patch("os.getenv")
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

        geteuid_mock.return_value = 0  # slave will not run as non-root
        pwdless_sudo_mock.return_value = True  # slave needs pwd-less sudo
        getenv_mock.return_value = None

        with mock.patch("builtins.open"):
            RemoteSlave.invoked(self_mock, ctx_mock)

        # slave server was created
        threaded_server_mock.assert_called_once()
        server = threaded_server_mock.return_value
        # the server was started
        server.start.assert_called_once()
