# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_testing_utils
================================

Test definitions for plainbox.impl.testing_utils module
"""

from unittest import TestCase
from warnings import warn, catch_warnings

from plainbox.impl.testing_utils import suppress_warnings


class SuppressWarningTests(TestCase):

    def test_suppress_warnings_works(self):
        """
        suppress_warnings() hides all warnings
        """
        @suppress_warnings
        def func():
            warn("this is a warning!")
        with catch_warnings(record=True) as warning_list:
            func()
        self.assertEqual(warning_list, [])

    def test_suppress_warnings_is_a_good_decorator(self):
        """
        suppress_warnings() does not clobber function name and docstring
        """
        @suppress_warnings
        def func_with_name():
            """and docstring"""
        self.assertEqual(func_with_name.__name__, 'func_with_name')
        self.assertEqual(func_with_name.__doc__, 'and docstring')
