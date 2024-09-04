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


def retry(
    f=None, *, max_attempts=5, initial_delay=1, backoff_factor=2, max_delay=60
):
    """
    Run the decorated function. If it fails, retry for up to max_attempts
    times, adding a backoff and a jitter on top of a delay of max_delay
    seconds. If none of the runs succeed, raise a SystemExit exception.
    """

    def decorator_retry(f):
        @functools.wraps(f)
        def _f(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                attempt_string = "Attempt {}/{}".format(attempt, max_attempts)
                print(attempt_string)
                print("=" * len(attempt_string))
                try:
                    result = f(*args, **kwargs)
                    return result
                except BaseException as e:
                    print("Attempt {} failed:\n{}".format(attempt, e))
                    print()
                    if attempt < max_attempts:
                        delay = min(
                            initial_delay * (backoff_factor**attempt),
                            max_delay,
                        )
                        jitter = random.uniform(
                            0, delay * 0.5
                        )  # Jitter: up to 50% of the delay
                        total_delay = delay + jitter
                        print(
                            "Waiting {:.2f} seconds before retrying...".format(
                                total_delay
                            )
                        )
                        time.sleep(total_delay)
                finally:
                    print()
            raise SystemExit("All the attempts have failed!")

        return _f

    if f is not None:
        return decorator_retry(f)

    return decorator_retry
