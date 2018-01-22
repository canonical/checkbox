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
plainbox.testing_utils.test_cwd
===============================

Test definitions for plainbox.testing_utils.cwd module
"""

import os
from tempfile import TemporaryDirectory
from unittest import TestCase

from plainbox.testing_utils.cwd import TestCwd


class TestCwdTest(TestCase):

    def test_usage(self):
        with TemporaryDirectory() as temp_dir:
            before = os.getcwd()
            with TestCwd(temp_dir) as test_cwd:
                self.assertEqual(test_cwd._saved_cwd, before)
                self.assertEqual(test_cwd._alternate_cwd, temp_dir)
                self.assertEqual(os.getcwd(), temp_dir)
            self.assertEqual(os.getcwd(), before)
