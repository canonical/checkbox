# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Massimimliano Girardi <massimiliano.girardi@canonical.com>
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

import time

from unittest import TestCase

from checkbox_support.helpers.timeout import run_with_timeout, timeout


class ClassSupport:
    def __init__(self, work_time):
        self.work_time = work_time

    def heavy_function(self):
        time.sleep(self.work_time)
        return "ClassSupport return value"


def heavy_function(time_s):
    time.sleep(time_s)
    return "ClassSupport return value"


def some_exception_raiser():
    raise ValueError("value error!")


def system_exit_raiser():
    raise SystemExit("abc")


def kwargs_args_support(first, second, third=3):
    return (first, second, third)


class TestTimeoutExec(TestCase):
    def test_class_field_timeouts(self):
        some = ClassSupport(1)
        with self.assertRaises(SystemExit):
            run_with_timeout(some.heavy_function, 0)

    def test_class_field_ok_return(self):
        some = ClassSupport(0)
        self.assertEqual(
            run_with_timeout(some.heavy_function, 10), "ClassSupport return value"
        )

    def test_function_timeouts(self):
        with self.assertRaises(SystemExit):
            run_with_timeout(heavy_function, 0, 10)

    def test_function_ok_return(self):
        self.assertEqual(
            run_with_timeout(heavy_function, 10, 0), "ClassSupport return value"
        )

    def test_function_exception_propagation(self):
        with self.assertRaises(ValueError):
            run_with_timeout(some_exception_raiser, 0)

    def test_function_systemexit_propagation(self):
        with self.assertRaises(SystemExit):
            system_exit_raiser()

    def test_function_args_kwargs_support(self):
        self.assertEqual(
            run_with_timeout(
                kwargs_args_support, 1, "first", "second", third="third"
            ),
            ("first", "second", "third"),
        )

    def test_decorator_test_ok(self):
        @timeout(1)
        def f(first, second, third):
            return (first, second, third)

        self.assertEqual(f(1, 2, 3), (1, 2, 3))

    def test_decorator_test_fail(self):
        @timeout(0)
        def f(first, second, third):
            time.sleep(100)
            return (first, second, third)

        with self.assertRaises(SystemExit):
            f(1, 2, 3)

    def test_decorator_exception(self):
        @timeout(1)
        def f(first, second, third):
            raise ValueError("error with first")

        with self.assertRaises(ValueError):
            f(1,2,3)
