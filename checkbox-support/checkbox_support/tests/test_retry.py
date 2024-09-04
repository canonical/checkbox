# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

from unittest import TestCase
from unittest.mock import patch
from io import StringIO

from checkbox_support.helpers.retry import retry


class TestRetry(TestCase):
    def test_decorator_ok(self):
        @retry
        def f(first, second, third):
            return (first, second, third)

        self.assertEqual(f(1, 2, 3), (1, 2, 3))

    @patch("checkbox_support.helpers.retry.time.sleep")
    def test_decorator_fail(self, mock_sleep):
        @retry
        def f():
            return 1 / 0

        with self.assertRaises(SystemExit):
            f()

    @patch("checkbox_support.helpers.retry.time.sleep")
    @patch("sys.stdout", new_callable=StringIO)
    def test_decorator_max_attempts(self, mock_stdout, mock_sleep):
        @retry(max_attempts=7)
        def f():
            return 1 / 0

        with self.assertRaises(SystemExit):
            f()
        self.assertIn("Attempt 7 failed", mock_stdout.getvalue())
        self.assertNotIn("Attempt 8 failed", mock_stdout.getvalue())
