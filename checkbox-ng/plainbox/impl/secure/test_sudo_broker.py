# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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

from subprocess import CalledProcessError
from unittest import TestCase, mock

from plainbox.impl.secure.sudo_broker import is_passwordless_sudo


class IsPasswordlessSudoTests(TestCase):
    @mock.patch("os.geteuid", return_value=0)
    @mock.patch("plainbox.impl.secure.sudo_broker.check_call")
    def test_root_happy(self, mock_check_call, mock_getuid):
        mock_check_call.return_value = 0
        self.assertTrue(is_passwordless_sudo())

    @mock.patch("os.geteuid", return_value=0)
    @mock.patch("plainbox.impl.secure.sudo_broker.check_call")
    def test_root_raising(self, mock_check_call, mock_getuid):
        mock_check_call.side_effect = OSError

        with self.assertRaises(SystemExit):
            is_passwordless_sudo()

    @mock.patch("os.geteuid", return_value=1000)
    @mock.patch("plainbox.impl.secure.sudo_broker.check_call")
    def test_non_root_happy(self, mock_check_call, mock_getuid):
        mock_check_call.return_value = 0
        self.assertTrue(is_passwordless_sudo())

    @mock.patch("os.geteuid", return_value=1000)
    @mock.patch("plainbox.impl.secure.sudo_broker.check_call")
    def test_non_root_raising(self, mock_check_call, mock_getuid):
        mock_check_call.side_effect = CalledProcessError(1, "oops")
        self.assertFalse(is_passwordless_sudo())
