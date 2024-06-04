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
"""
checkbox_support.helpers.timeout
=============================================

Utility class that provides functionalities connected to placing timeouts on
functions
"""
import os
import time
import traceback
import subprocess
import multiprocessing

from functools import partial
from contextlib import wraps
from unittest.mock import patch


def run_with_timeout(f, timeout_s, *args, **kwargs):
    """
    Runs a function with the given args and kwargs. If the function doesn't
    terminate within timeout_s seconds, this raises TimeoutError the function
    and any process it may have started.

    Note: the function, *args and **kwargs must be picklable to use this.
    """
    result_queue = multiprocessing.SimpleQueue()
    exception_queue = multiprocessing.SimpleQueue()

    def _f(*args, **kwargs):
        os.setsid()
        try:
            result_queue.put(f(*args, **kwargs))
        except BaseException as e:
            try:
                exception_queue.put(e)
            except AttributeError:
                # raised by pickle.dumps in put when an exception is not
                # pickleable. This raises SystemExit as we can't preserve the
                # exception type, so any exception handler in the function
                # user will not work (or will wrongly handle the exception
                # if we change the type
                exception_queue.put(
                    SystemExit(
                        "".join(
                            [
                                "Function failed but the timeout decorator is "
                                "unable to propagate this un-picklable "
                                "exception:\n"
                            ]
                            + traceback.format_exception(e)
                        )
                    )
                )

    process = multiprocessing.Process(
        target=_f, args=args, kwargs=kwargs, daemon=True
    )
    process.start()
    process.join(timeout_s)

    if process.is_alive():
        subprocess.run("kill -9 -- -{}".format(process.pid), shell=True)
        raise TimeoutError("Task unable to finish in {}s".format(timeout_s))
    if not exception_queue.empty():
        raise exception_queue.get()
    return result_queue.get()


def timeout(timeout_s):
    """
    Lets the decorated function run for up to timeout_s seconds. If the
    function doesn't terminate within the timeout, raises TimeoutError
    """

    def timeout_timeout_s(f):
        @wraps(f)
        def _f(*args, **kwargs):
            return run_with_timeout(f, timeout_s, *args, **kwargs)

        return _f

    return timeout_timeout_s


def fake_run_with_timeout(f, timeout_s, *args, **kwargs):
    return f(*args, **kwargs)


mock_timeout = partial(
    patch,
    "checkbox_support.helpers.timeout.run_with_timeout",
    new=fake_run_with_timeout,
)
