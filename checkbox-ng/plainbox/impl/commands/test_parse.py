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
plainbox.impl.commands.test_parse
=================================

Test definitions for plainbox.impl.commands.parse module
"""

import argparse
from inspect import cleandoc
from unittest import TestCase

import mock

from plainbox.impl.parsers import all_parsers
from plainbox.impl.parsers import ParserPlugIn
from plainbox.impl.commands.parse import ParseCommand
from plainbox.testing_utils.io import TestIO


class TestParseCommand(TestCase):

    def setUp(self):
        self.ns = mock.Mock()

    def test_init(self):
        ParseCommand()

    _help = """
usage: test parse [-h] PARSER-NAME

This command can be used to invoke any of the parsers exposed to the
`plainbox.parsers` entry point, parse standard input and produce a JSON dump
of the resulting data structure on stdout. Keep in mind that most parsers were
designed with the 'C' locale in mind. You may have to override the environment
variable LANG to "C".

positional arguments:
  PARSER-NAME  Name of the parser to use

optional arguments:
  -h, --help   show this help message and exit

Example: LANG=C pactl list | plainbox dev parse pactl-list
"""

    maxDiff = None

    def test_register_parser(self):
        # Create an argument parser
        parser = argparse.ArgumentParser(prog='test')
        # Add subparsers to it
        subparsers = parser.add_subparsers()
        # Register the ParseCommand into subparsers
        ParseCommand().register_parser(subparsers)
        # With IO capture helper
        with TestIO() as io:
            # Print the help message
            parser.print_help()
        # Ensure that a short help message was included
        self.assertIn("parse stdin with the specified parser", io.stdout)
        # With another IO capture helper
        with TestIO() as io:
            # With a trap for SystemExit exception
            with self.assertRaises(SystemExit):
                # Run the 'parse --help' command
                parser.parse_args(['parse', '--help'])
        # Ensure that a detailed help message was printed
        self.assertEqual(io.stdout, cleandoc(self._help) + '\n')

    @mock.patch("plainbox.impl.commands.parse.ParseInvocation")
    def test_invoked(self, patched_ParseInvocation):
        # Make a fake ParserPlugIn
        mock_parser = mock.Mock(spec=ParserPlugIn)
        # Give it a plugin_name and summary
        mock_parser.plugin_name = "foo"
        mock_parser.summary = "summary of foo"
        # With temporary override to use the fake parser
        with all_parsers.fake_plugins([mock_parser]):
            # Set the name of the expected parser to 'foo'
            self.ns.parser_name = 'foo'
            # And invoke the ParseCommand
            retval = ParseCommand().invoked(self.ns)
        # Ensure that ParseInvocation was called with the fake parser
        patched_ParseInvocation.assert_called_once_with(mock_parser)
        # Ensure that ParsesCommand.invoked() returned whatever
        # was returned by ParseInvocation.run()
        self.assertEqual(
            retval,
            patched_ParseInvocation(self.ns.parser_name).run.return_value)

    def test_invoked_question_mark(self):
        # Make a fake ParserPlugIn
        mock_parser = mock.Mock(spec=ParserPlugIn)
        # Give it a plugin_name, name and summary
        mock_parser.plugin_name = "foo"
        mock_parser.name = "foo"
        mock_parser.summary = "summary of foo"
        # With temporary override to use the fake parser
        with all_parsers.fake_plugins([mock_parser]):
            # Set the name of the expected parser to '?'
            self.ns.parser_name = '?'
            # With IO capture helper
            with TestIO() as io:
                # And invoke the ParseCommand
                retval = ParseCommand().invoked(self.ns)
        # Ensure that a list of parsers was printed
        self.assertEqual(
            io.stdout, cleandoc(
                """
                The following parsers are available:
                  foo: summary of foo
                """) + '\n')
        # Ensure that the return code was 0
        self.assertEqual(retval, 0)
