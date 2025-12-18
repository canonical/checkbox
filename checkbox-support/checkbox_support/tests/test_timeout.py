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
import os
import time
import subprocess
import multiprocessing

from queue import Empty
from unittest import TestCase
from unittest.mock import patch

from checkbox_support.helpers.timeout import (
    timeout,
    is_picklable,
    run_with_timeout,
    fake_run_with_timeout,
    kill_tree,
)


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
        with self.assertRaises(TimeoutError):
            run_with_timeout(some.heavy_function, 0.1)

    def test_class_field_ok_return(self):
        some = ClassSupport(0)
        self.assertEqual(
            run_with_timeout(some.heavy_function, 10),
            "ClassSupport return value",
        )

    def test_function_timeouts(self):
        with self.assertRaises(TimeoutError):
            run_with_timeout(heavy_function, 0.1, 10)

    def test_function_ok_return(self):
        self.assertEqual(
            run_with_timeout(heavy_function, 10, 0.1),
            "ClassSupport return value",
        )

    def test_function_exception_propagation(self):
        with self.assertRaises(ValueError):
            run_with_timeout(some_exception_raiser, 1)

    @patch("checkbox_support.helpers.timeout.Process.join")
    def test_function_exception_propagation_in_process(self, mock_join):
        mock_join.side_effect = KeyboardInterrupt()
        with self.assertRaises(BaseException):
            run_with_timeout(heavy_function, 1)

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
        @timeout(0.1)
        def f(first, second, third):
            time.sleep(100)
            return (first, second, third)

        with self.assertRaises(TimeoutError):
            f(1, 2, 3)

    def test_decorator_exception(self):
        @timeout(1)
        def f(first, second, third):
            raise ValueError("error with first")

        with self.assertRaises(ValueError):
            f(1, 2, 3)

    def test_identity(self):
        def k(*args, **kwargs):
            return (args, kwargs)

        self.assertEqual(
            k(1, 2, 3, abc=10), fake_run_with_timeout(k, 100, 1, 2, 3, abc=10)
        )

    def test_unpicklable_return_raises(self):
        """
        The reason why this raises is that the timeout decorator pushes the
        function to another process. Trying to return an un-picklable object
        will raise a pickle error.
        """

        @timeout(1)
        def k():
            return lambda x: ...

        with self.assertRaises(SystemExit):
            k()

    def test_unpicklable_raise_raises(self):
        """
        The reason why this raises is that the timeout decorator pushes the
        function to another process. Trying to raise an un-picklable object
        will raise a pickle error.
        """

        @timeout(1)
        def k():
            raise ValueError(lambda x: ...)

        with self.assertRaises(SystemExit):
            k()

    def test_timeout_kills_subprocess_tree_on_timeout(self):
        """
        This tests that the timeout decorator not only kills the direct child
        (function under test) but also any sub-process it has spawned. This
        is done because one could `subprocess.run` a long-lived process from
        the function and it could cause mayhem (and block the test session as
        Checkbox waits for all children to be done)
        """

        def inner():
            time.sleep(1e4)

        def outer():
            inner_p = multiprocessing.Process(target=inner)
            inner_p.start()
            inner_p.join()

        @timeout(0.1)
        def f():
            outer_p = multiprocessing.Process(target=outer)
            outer_p.start()
            outer_p.join()

        with self.assertRaises(TimeoutError):
            f()
        # give the process a few ms to wind down
        time.sleep(0.1)
        self.assertEqual(multiprocessing.active_children(), [])

    @patch("checkbox_support.helpers.timeout.Queue")
    @patch("checkbox_support.helpers.timeout.Process")
    def test_run_with_timeout_double_get(self, process_mock, queue_mock):
        process_mock().is_alive.return_value = False
        queue_mock().get_nowait.side_effect = Empty()
        queue_mock().get.side_effect = [
            Empty(),
            ValueError("Some value error"),
        ]

        with self.assertRaises(ValueError):
            run_with_timeout(lambda: ..., 0.1)

    @patch("checkbox_support.helpers.timeout.Queue")
    @patch("checkbox_support.helpers.timeout.Process")
    def test_run_with_timeout_system_exit_no_get(
        self, process_mock, queue_mock
    ):
        process_mock().is_alive.return_value = False
        queue_mock().get_nowait.side_effect = Empty()
        queue_mock().get.side_effect = Empty()

        with self.assertRaises(SystemExit):
            run_with_timeout(lambda: ..., 0.1)

    def test_is_picklable(self):
        self.assertFalse(is_picklable(lambda: ...))
        self.assertTrue(is_picklable([1, 2, 3]))

    @patch("shutil.which")
    @patch("subprocess.check_call")
    @patch("subprocess.run")
    def test_kill_tree_fallback(self, run_mock, check_call_mock, which_mock):
        which_mock.return_value = None
        check_call_mock.side_effect = subprocess.CalledProcessError(
            1, "Some cmd"
        )

        kill_tree(123)
        # kill_tree tried to search for known consoles
        self.assertTrue(which_mock.called)
        # kill_tree also tried to run the default shell to see if kill supports
        # the -PID semantic
        self.assertTrue(check_call_mock.called)
        # finally the function tried to call kill without the - as a last ditch
        # tentative
        self.assertTrue(run_mock.called)
