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
plainbox.impl.commands.test_dev
===============================

Test definitions for plainbox.impl.dev module
"""

import argparse
from inspect import cleandoc
from unittest import TestCase

import mock

from plainbox.impl.commands.dev import DevCommand
from plainbox.testing_utils.io import TestIO


class TestDevCommand(TestCase):

    def setUp(self):
        self.parser = argparse.ArgumentParser(prog='test')
        self.subparsers = self.parser.add_subparsers()
        self.checkbox = mock.Mock()
        self.config = mock.Mock()
        self.ns = mock.Mock()

    def test_init(self):
        dev_cmd = DevCommand(self.checkbox, self.config)
        self.assertIs(dev_cmd.checkbox, self.checkbox)
        self.assertIs(dev_cmd.config, self.config)

    def test_register_parser(self):
        DevCommand(self.checkbox, self.config).register_parser(
            self.subparsers)
        with TestIO() as io:
            self.parser.print_help()
        self.assertIn("development commands", io.stdout)
        with TestIO() as io:
            with self.assertRaises(SystemExit):
                self.parser.parse_args(['dev', '--help'])
        self.maxDiff = None
        self.assertEqual(
            io.stdout, cleandoc(
                """
                usage: test dev [-h] {script,special} ...

                positional arguments:
                  {script,special}
                    script          run a command from a job
                    special         special/internal commands

                optional arguments:
                  -h, --help        show this help message and exit
                """)
            + "\n")
