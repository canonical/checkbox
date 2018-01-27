# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.testing_utils.io` -- tools for testing IO
========================================================

Implementation of context managers for observing IO
"""

from io import StringIO
import sys


class TestIO:
    """
    Helper class for capturing stdin, stdout, stderr IO for testing
    """

    def __init__(self, *, input=None, combined=False):
        self._combined = combined
        self._input = input

    def __enter__(self):
        # Remember the real objects that we'll replace
        self._real_stdin = sys.stdin
        self._real_stdout = sys.stdout
        self._real_stderr = sys.stderr
        # Create fake objects. In combined mode the output is more similar to
        # what a user at a console would see (stdout and stderr are
        # intertwined)
        self._fake_stdin = StringIO(self._input)
        if self._combined:
            self._fake_combined = StringIO()
        else:
            self._fake_stdout = StringIO()
            self._fake_stderr = StringIO()
        # Stub-away .close()
        if self._combined:
            self._fake_combined.close = lambda: None
        else:
            self._fake_stdout.close = lambda: None
            self._fake_stderr.close = lambda: None
        # Lastly replace the real objects
        sys.stdin = self._fake_stdin
        if self._combined:
            sys.stdout = self._fake_combined
            sys.stderr = self._fake_combined
        else:
            sys.stdout = self._fake_stdout
            sys.stderr = self._fake_stderr
        return self

    def __exit__(self, *exc):
        # Save the data that was written to stdout and stderr
        if self._combined:
            self._test_combined = self._fake_combined.getvalue()
        else:
            self._test_stdout = self._fake_stdout.getvalue()
            self._test_stderr = self._fake_stderr.getvalue()
        # Close all fake streams
        self._fake_stdin.close()
        if self._combined:
            self._fake_combined.close()
        else:
            self._fake_stdout.close()
            self._fake_stderr.close()
        # And restore original streams
        sys.stdin = self._real_stdin
        sys.stdout = self._real_stdout
        sys.stderr = self._real_stderr

    @property
    def stdout(self):
        """
        All stdout output
        """
        return self._test_stdout

    @property
    def stderr(self):
        """
        All stderr output
        """
        return self._test_stderr

    @property
    def combined(self):
        """
        All output combined from stdout and stderr
        """
        return self._test_combined
