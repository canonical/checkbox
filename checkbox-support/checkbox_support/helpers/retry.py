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
"""
checkbox_support.helpers.retry
=============================================

Utility class providing functionalities to let functions retry with a
delay, backoff and jitter.
"""
import functools
import random
import time
from unittest.mock import patch


def run_with_retry(f, max_attempts, delay, *args, **kwargs):
    """
    Run the f function. If it fails, retry for up to max_attempts times, adding
    a backoff and a jitter on top of a delay (in seconds). If none of the runs
    succeed, raise the encountered exception.
    """
    initial_delay = 1
    backoff_factor = 2
    if max_attempts < 1:
        raise ValueError(
            "max_attempts should be at least 1 ({} was used)".format(
                max_attempts
            )
        )
    if delay < 1:
        raise ValueError(
            "delay should be at least 1 ({} was used)".format(delay)
        )
    for attempt in range(1, max_attempts + 1):
        attempt_string = "Attempt {}/{} (function '{}')".format(
            attempt, max_attempts, f.__name__
        )
        print()
        print("=" * len(attempt_string))
        print(attempt_string)
        print("=" * len(attempt_string))
        try:
            result = f(*args, **kwargs)
            return result
        except BaseException as e:
            print("Attempt {} failed:".format(attempt))
            print(e)
            print()
            if attempt >= max_attempts:
                print("All the attempts have failed!")
                raise
            min_delay = min(
                initial_delay * (backoff_factor**attempt),
                delay,
            )
            jitter = random.uniform(
                0, delay * 0.5
            )  # Jitter: up to 50% of the delay
            total_delay = min_delay + jitter
            print(
                "Waiting {:.2f} seconds before retrying...".format(total_delay)
            )
            time.sleep(total_delay)


def retry(max_attempts, delay):
    """
    Run the decorated function. If it fails, retry for up to max_attempts
    times, adding a backoff and a jitter on top of a delay (in seconds).
    If none of the runs succeed, raise the encountered exception.
    """

    def decorator_retry(f):
        @functools.wraps(f)
        def _f(*args, **kwargs):
            return run_with_retry(f, max_attempts, delay, *args, **kwargs)

        return _f

    return decorator_retry


def fake_run_with_retry(f, max_attempts, delay, *args, **kwargs):
    return f(*args, **kwargs)


mock_retry = functools.partial(
    patch,
    "checkbox_support.helpers.retry.run_with_retry",
    new=fake_run_with_retry,
)
