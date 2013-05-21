# This file is part of Checkbox.
#
# Copyright 2012-2013 Canonical Ltd.
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
checkbox_ng.test_main
=====================

Test definitions for checkbox_ng.main module
"""

from inspect import cleandoc
from unittest import TestCase

from plainbox.testing_utils.io import TestIO

from checkbox_ng import __version__ as version
from checkbox_ng.main import main


class TestMain(TestCase):

    def test_version(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--version'])
            self.assertEqual(call.exception.args, (0,))
        self.assertEqual(io.combined, "{}.{}.{}\n".format(*version[:3]))

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--help'])
        self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: checkbox [-h] [-v] {sru,check-config,script} ...

        positional arguments:
          {sru,check-config,script}
            sru                 run automated stable release update tests
            check-config        check and display plainbox configuration
            script              run a command from a job

        optional arguments:
          -h, --help            show this help message and exit
          -v, --version         show program's version number and exit
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_without_args(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main([])
            self.assertEqual(call.exception.args, (2,))
        expected = """
        usage: checkbox [-h] [-v] {sru,check-config,script} ...
        checkbox: error: too few arguments
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")
