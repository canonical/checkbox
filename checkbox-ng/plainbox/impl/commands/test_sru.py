# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.commands.test_sru
===============================

Test definitions for plainbox.impl.box module
"""

from inspect import cleandoc
from unittest import TestCase

from plainbox.impl.box import main
from plainbox.testing_utils.io import TestIO


class TestSru(TestCase):

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['sru', '--help'])
            self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox sru [-h] [--destination URL] SECURE-ID FALLBACK-FILE

        positional arguments:
          SECURE-ID          Associate submission with a machine using this SECURE-ID
          FALLBACK-FILE      If submission fails save the test report as FALLBACK-FILE

        optional arguments:
          -h, --help         show this help message and exit
          --destination URL  POST the test report XML to this URL
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")
