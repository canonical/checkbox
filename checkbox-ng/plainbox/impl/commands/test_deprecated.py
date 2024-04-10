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


class DeprecatedTests(TestCase):
    @mock.patch("warnings.warn")
    def test_parse_warning(self, warn_mock):
        import plainbox.impl.commands.parse

        self.assertTrue(warn_mock.called)

    @mock.patch("warnings.warn")
    def test_session_warning(self, warn_mock):
        import plainbox.impl.commands.session

        self.assertTrue(warn_mock.called)
