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
import subprocess
import multiprocessing

from contextlib import wraps


def run_with_timeout(f, timeout_s, *args, **kwargs):
    """
    Runs a function with the given args and kwargs. If the function doesn't
    terminate within timeout_s seconds, this raises TimeoutError the function
    and any process it may have started.

    Note: the function, *args and **kwargs must be picklable to use this.
    """
    result_queue = multiprocessing.Queue()
    exception_queue = multiprocessing.Queue()

    def _f(*args, **kwargs):
        os.setsid()
        try:
            result_queue.put(f(*args, **kwargs))
        except BaseException as e:
            exception_queue.put(e)

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
