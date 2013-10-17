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

from plainbox.impl.commands.dev import DevCommand
from plainbox.testing_utils.io import TestIO
from plainbox.vendor import mock


class TestDevCommand(TestCase):

    def setUp(self):
        self.parser = argparse.ArgumentParser(prog='test')
        self.subparsers = self.parser.add_subparsers()
        self.provider_list = [mock.Mock()]
        self.config = mock.Mock()
        self.ns = mock.Mock()

    def test_init(self):
        dev_cmd = DevCommand(self.provider_list, self.config)
        self.assertIs(dev_cmd.provider_list, self.provider_list)
        self.assertIs(dev_cmd.config, self.config)

    def test_register_parser(self):
        DevCommand(self.provider_list, self.config).register_parser(
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
                usage: test dev [-h] {script,special,analyze,parse,crash,logtest} ...

                positional arguments:
                  {script,special,analyze,parse,crash,logtest}
                    script              run a command from a job
                    special             special/internal commands
                    analyze             analyze how selected jobs would be executed
                    parse               parse stdin with the specified parser
                    crash               crash the application
                    logtest             log messages at various levels

                optional arguments:
                  -h, --help            show this help message and exit
                """)
            + "\n")
