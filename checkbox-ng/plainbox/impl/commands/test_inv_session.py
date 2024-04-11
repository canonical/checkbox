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

from plainbox.impl.commands.inv_session import SessionInvocation


class SessionInvocationTests(TestCase):
    @mock.patch(
        "plainbox.impl.commands.inv_session.SessionInvocation._lookup_storage"
    )
    @mock.patch("builtins.print")
    def test_register_parser_none(self, print_mock, lookup_mock):
        lookup_mock.return_value = None
        ns = mock.MagicMock()
        ns.session_id_list = range(1)

        session_command = SessionInvocation(ns, None)
        session_command.show_session()

        self.assertTrue(print_mock.called)
