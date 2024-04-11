# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

"""
:mod:`checkbox_support.tests` -- auxiliary test loaders for the support library
===============================================================================
"""

from inspect import getabsfile
from unittest.loader import defaultTestLoader
from unittest import TestSuite
import os

import checkbox_support


def load_unit_tests():
    """
    Load all unit tests and return a TestSuite object
    """
    # Discover all unit tests. By simple convention those are kept in
    # python modules that start with the word 'test_' .
    start_dir = os.path.dirname(getabsfile(checkbox_support))
    top_level_dir = os.path.normpath(os.path.join(start_dir, ".."))
    test_suite = TestSuite()
    for path in os.listdir(start_dir):
        # skip tests that come from a vendorized code
        if path in ("__pycache__", "vendor"):
            continue
        path = os.path.join(start_dir, path)
        if os.path.isdir(path):
            test_suite.addTests(
                defaultTestLoader.discover(path, top_level_dir=top_level_dir)
            )
    return test_suite


def test_suite():
    """
    Test suite function used by setuptools test loader.

    Uses unittest test discovery system to get a list of test cases defined
    inside checkbox_support.
    See setup.py setup(test_suite=...) for a matching entry
    """
    return load_unit_tests()
