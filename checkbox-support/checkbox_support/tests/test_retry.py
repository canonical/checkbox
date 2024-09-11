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

from checkbox_support.helpers.retry import fake_run_with_retry, retry


class TestRetry(TestCase):
    @patch("time.sleep")
    def test_decorator_ok(self, mock_sleep):
        @retry(5, 10)
        def f(first, second, third):
            return (first, second, third)

        self.assertEqual(f(1, 2, 3), (1, 2, 3))

    @patch("time.sleep")
    def test_decorator_fail(self, mock_sleep):
        @retry(3, 10)
        def f():
            return 1 / 0

        with self.assertRaises(ZeroDivisionError):
            f()

    @patch("time.sleep")
    @patch("sys.stdout", new_callable=StringIO)
    def test_decorator_max_attempts(self, mock_stdout, mock_sleep):
        @retry(max_attempts=7, delay=10)
        def f():
            return 1 / 0

        with self.assertRaises(ZeroDivisionError):
            f()
        self.assertIn("Attempt 7 failed", mock_stdout.getvalue())
        self.assertNotIn("Attempt 8 failed", mock_stdout.getvalue())

    def test_decorator_wrong_max_attempts(self):
        @retry(-1, 10)
        def f():
            return 1 / 0

        with self.assertRaises(ValueError):
            f()

    def test_decorator_wrong_delay(self):
        @retry(2, -1)
        def f():
            return 1 / 0

        with self.assertRaises(ValueError):
            f()

    def test_identity(self):
        def k(*args, **kwargs):
            return (args, kwargs)

        self.assertEqual(
            k(1, 2, 3, abc=10), fake_run_with_retry(k, 5, 10, 1, 2, 3, abc=10)
        )
