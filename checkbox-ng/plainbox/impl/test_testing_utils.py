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
import os

from plainbox.impl.rfc822 import PythonFileTextSource
from plainbox.impl.testing_utils import make_job
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


class MakeJobTests(TestCase):
    """
    Tests for the make_job() function
    """

    def setUp(self):
        self.job = make_job('job')

    def test_origin_is_set(self):
        """
        verify that jobs created with make_job() have a non-None origin
        """
        self.assertIsNot(self.job.origin, None)

    def test_origin_source_is_special(self):
        """
        verify that jobs created with make_job() use PythonFileTextSource as
        the origin.source attribute.
        """
        self.assertIsInstance(self.job.origin.source, PythonFileTextSource)

    def test_origin_source_filename_is_correct(self):
        """
        verify that make_job() can properly trace the filename of the python
        module that called make_job()
        """
        self.assertEqual(
            os.path.basename(self.job.origin.source.filename),
            "test_testing_utils.py")
