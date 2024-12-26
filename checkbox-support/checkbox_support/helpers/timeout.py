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
import shutil
import pickle
import traceback
import subprocess

from queue import Empty
from functools import partial
from unittest.mock import patch
from contextlib import wraps, suppress
from multiprocessing import Process, Queue


def is_picklable(value):
    """
    This function checks if an object is picklable. This is used here because
    to propagate a value via a multiprocessing queue, it has to be picklable.
    If it is not, when using normal Queues (not SimpleQueues), pushing the
    value in the queue will crash the encoder Thread that the Queue contains,
    silently failing the operation.
    """
    with suppress(pickle.PicklingError), suppress(AttributeError):
        _ = pickle.dumps(value)
        return True
    return False


def kill_tree(pid):
    """
    Kill a process tree

    This tries to force the shell to what we want instead of letting the system
    decide. This is because `sh` kill doesn't support tree kill (-PID), so we
    would rather avoid it
    """
    if shutil.which("bash"):
        return subprocess.run(["bash", "-c", "kill -9 -{}".format(pid)])
    elif shutil.which("zsh"):
        return subprocess.run(["zsh", "-c", "kill -9 -{}".format(pid)])
    with suppress(subprocess.CalledProcessError):
        # if SHELL is sh or doesn't support -XX pid, this will fail
        return subprocess.check_call("kill -9 -{}".format(pid), shell=True)
    # lets at least kill the direct pid
    return subprocess.run("kill -9 {}".format(pid), shell=True)


def run_with_timeout(f, timeout_s, *args, **kwargs):
    """
    Runs a function with the given args and kwargs. If the function doesn't
    terminate within timeout_s seconds, this raises TimeoutError the function
    and any process it may have started.

    Note: the function, *args and **kwargs must be picklable to use this.
    """
    assert timeout_s > 0, "Timeout must be more than 0"
    result_queue = Queue()
    exception_queue = Queue()

    def _f(*args, **kwargs):
        os.setsid()
        try:
            result = f(*args, **kwargs)
            if is_picklable(result):
                result_queue.put(result)
            else:
                exception_queue.put(
                    SystemExit(
                        "Function tried to return non-picklable value "
                        "but this is not supported by the timeout decorator.\n"
                        "Returned object:\n" + repr(result)
                    )
                )
            result_queue.close()
            exception_queue.close()
            return
        except BaseException as e:
            error = e

        if is_picklable(error):
            exception_queue.put(error)
            result_queue.close()
            exception_queue.close()
            return
        # raised by pickle.dumps in put when an exception is not
        # pickleable. This raises SystemExit as we can't preserve the
        # exception type, so any exception handler in the function
        # user will not work (or will wrongly handle the exception
        # if we change the type)
        exception_queue.put(
            SystemExit(
                "".join(
                    [
                        "Function failed but the timeout decorator is "
                        "unable to propagate this un-picklable "
                        "exception:\n"
                    ]
                    + traceback.format_exception(type(error), error, None)
                )
            )
        )
        result_queue.close()
        exception_queue.close()

    process = Process(target=_f, args=args, kwargs=kwargs)
    process.start()
    process.join(timeout_s)

    if process.is_alive():
        # this tries to kill the whole process tree, not just the child.
        kill_tree(process.pid)
        raise TimeoutError("Task unable to finish in {}s".format(timeout_s))

    with suppress(Empty):
        return result_queue.get_nowait()
    with suppress(Empty):
        raise exception_queue.get_nowait()

    # unpickling is done in a separate thread, could it be un-scheduled yet?
    with suppress(Empty):
        return result_queue.get(timeout=0.1)
    with suppress(Empty):
        raise exception_queue.get(timeout=0.1)

    # this should never happen, lets crash the program if it does
    raise SystemExit(
        "Function failed to propagate either a value or an exception.\n"
        "It is unclear why this happened or what the underlying function "
        "did."
    )


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
