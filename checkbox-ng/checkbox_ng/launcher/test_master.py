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

from checkbox_ng.launcher.master import RemoteMaster


class MasterTests(TestCase):
    @mock.patch("ipaddress.ip_address")
    @mock.patch("time.time")
    @mock.patch("builtins.print")
    @mock.patch("os.path.exists")
    @mock.patch("checkbox_ng.launcher.master.Configuration.from_text")
    @mock.patch("checkbox_ng.launcher.master._")
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
            RemoteMaster.invoked(self_mock, ctx_mock)

        self.assertTrue(self_mock.connect_and_run.called)

    @mock.patch("checkbox_ng.launcher.master.RemoteSessionAssistant")
    @mock.patch("checkbox_ng.launcher.master._")
    def test_check_remote_api_match_ok(
        self, gettext_mock, remote_assistant_mock
    ):
        """
        Test that the check_remote_api_match function does not fail/crash
        if the two versions match
        """
        self_mock = mock.MagicMock()
        session_assistant_mock = mock.MagicMock()
        self_mock.sa = session_assistant_mock

        remote_assistant_mock.REMOTE_API_VERSION = 0
        session_assistant_mock.get_remote_api_version.return_value = 0

        RemoteMaster.check_remote_api_match(self_mock)
        # assert this runs with no problem, the two versions are the same
        self.assertTrue(True)

    @mock.patch("checkbox_ng.launcher.master.RemoteSessionAssistant")
    @mock.patch("checkbox_ng.launcher.master._")
    def test_check_remote_api_match_fail(
        self, gettext_mock, remote_assistant_mock
    ):
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
            RemoteMaster.check_remote_api_match(self_mock)

        remote_assistant_mock.REMOTE_API_VERSION = 0
        session_assistant_mock.get_remote_api_version.return_value = 1

        with self.assertRaises(SystemExit):
            # this should also exit checkbox because the two versions are
            # different
            RemoteMaster.check_remote_api_match(self_mock)
