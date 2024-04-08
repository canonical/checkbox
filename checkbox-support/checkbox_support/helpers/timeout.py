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
import signal
import psutil
import multiprocessing

from contextlib import wraps, suppress


def kill_proc_tree(pid):
    """
    Best effort kill a process tree (including grandchildren)
    """
    process = psutil.Process(pid)
    children = process.children(recursive=True)
    for p in children:
        with suppress(psutil.NoSuchProcess):
            p.send_signal(signal.SIGTERM)
    gone, alive = psutil.wait_procs(children, timeout=1)  # s
    alive += process.children(recursive=True)
    process.send_signal(signal.SIGKILL)
    for p in alive:
        with suppress(psutil.NoSuchProcess):
            p.send_signal(signal.SIGKILL)
    return psutil.wait_procs(alive, timeout=1)  # s


def run_with_timeout(f, timeout_s, *args, **kwargs):
    """
    Runs a function with the given args and kwargs. If the function doesn't
    terminate within timeout_s seconds, this raises SystemExit because the
    expiration of the timeout does not terminate the underlying task, therefore
    the process should exit to reach that goal.
    """
    result_queue = multiprocessing.Queue()
    exception_queue = multiprocessing.Queue()

    def _f(*args, **kwargs):
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
        # we must kill the full process tree to not leave any process orphaned
        import subprocess
        subprocess.run(["kill", "-9", "-{}".format(process.pid)])
        #kill_proc_tree(process.pid)
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


@timeout(1)
def main():
    import subprocess

    subprocess.check_call(["sleep", "10000"])


if __name__ == "__main__":
    main()
