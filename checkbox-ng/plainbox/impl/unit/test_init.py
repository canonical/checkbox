# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

"""
plainbox.impl.unit.test_init
============================

Test definitions for plainbox.impl.unit (package init file)
"""

from unittest import TestCase

from plainbox.impl.unit import get_accessed_parameters


class FunctionTests(TestCase):

    def test_get_accessed_parameters(self):
        self.assertEqual(
            get_accessed_parameters("some text"), frozenset())
        self.assertEqual(
            get_accessed_parameters("some {parametric} text"),
            frozenset(['parametric']))
        self.assertEqual(
            get_accessed_parameters("some {} text"),
            frozenset(['']))
        self.assertEqual(
            get_accessed_parameters("some {1} {2} {3} text"),
            frozenset(['1', '2', '3']))
