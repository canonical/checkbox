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
import threading

from queue import Queue
from contextlib import wraps


def run_with_timeout(f, timeout_s, *args, **kwargs):
    """
    Runs a function with the given args and kwargs. If the function doesn't
    terminate within timeout_s seconds, this raises SystemExit because the
    expiration of the timeout does not terminate the underlying task, therefore
    the process should exit to reach that goal.
    """
    result_queue = Queue()
    exception_queue = Queue()

    def _f(*args, **kwargs):
        try:
            result_queue.put(f(*args, **kwargs))
        except BaseException as e:
            exception_queue.put(e)

    thread = threading.Thread(target=_f, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    thread.join(timeout_s)

    if thread.is_alive():
        raise SystemExit(
            "Task unable to finish in {}s".format(timeout_s)
        ) from TimeoutError
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
