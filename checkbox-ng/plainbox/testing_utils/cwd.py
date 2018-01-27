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
:mod:`plainbox.testing_utils.cwd` -- tools for testing in another directory
===========================================================================

Implementation of context managers for working in another directory
"""

import os


class TestCwd:
    """
    Context manager for doing some operations in another directory
    """

    def __init__(self, alternate_cwd):
        self._alternate_cwd = alternate_cwd
        self._saved_cwd = None

    def __enter__(self):
        self._saved_cwd = os.getcwd()
        os.chdir(self._alternate_cwd)
        return self

    def __exit__(self, *args):
        os.chdir(self._saved_cwd)
        self._saved_cwd = None
