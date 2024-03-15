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


def timeout_run(f, timeout_s, *args, **kwargs):
    """
    Runs a function with the given args and kwargs. If the function doesn't
    terminate within timeout_s seconds, this raises TimeoutError.
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
        raise TimeoutError("Task unable to finish in {}s".format(timeout_s))
    if not exception_queue.empty():
        raise exception_queue.get()
    return result_queue.get()


def timeout(timeout_s):
    def timeout_timeout_s(f):
        @wraps(f)
        def _f(*args, **kwargs):
            return timeout_run(f, timeout_s, *args, **kwargs)

        return _f

    return timeout_timeout_s
