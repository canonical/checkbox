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

"""
:mod:`plainbox.impl.commands.parser` -- parser sub-command
==========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import io
import logging
import sys

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.parsers import all_parsers


logger = logging.getLogger("plainbox.commands.parse")


class ParseInvocation:
    """
    Invocation of the 'parse' command
    """

    def __init__(self, parser, encoding='UTF-8'):
        self.parser = parser
        self.encoding = encoding

    def run(self):
        # This little trick is required to get around 'ascii' encoding that
        # stdin unfortunately has when piped to. Using the embedded 'buffer'
        # attribute of sys.stdin we can construct a TextIOWrapper with
        # different, arbitrary encoding.
        if (isinstance(sys.stdin, io.TextIOWrapper)
                and sys.stdin.encoding != self.encoding):
            with io.TextIOWrapper(sys.stdin.buffer, encoding='UTF-8') as stdin:
                text = self._do_read(stdin)
        else:
            text = self._do_read(sys.stdin)
        # If we didn't manage to read text from stdin, abort
        if text is None:
            return 1
        # Parse all input and get the json representation
        json_text = self.parser.parse_text_to_json(text)
        # If we didn't manage to parse input, abort
        if json_text is None:
            return 2
        # Print the json representation
        print(json_text)
        return 0

    def _do_read(self, stream):
        try:
            return stream.read()
        except UnicodeEncodeError:
            print(_("Unable to decode input stream, must be valid UTF-8"),
                  file=sys.stderr)
            return None


class ParseCommand(PlainBoxCommand):
    """
    Command for running any of the checkbox parsers
    """

    def __init__(self):
        self.parser_collection = all_parsers
        self.parser_collection.load()

    def invoked(self, ns):
        if ns.parser_name == '?':
            return self._print_parser_list()
        else:
            parser = self.parser_collection.get_by_name(ns.parser_name)
            return ParseInvocation(parser).run()

    def _print_parser_list(self):
        print(_("The following parsers are available:"))
        for parser in self.parser_collection.get_all_plugins():
            print("  {}: {}".format(parser.name, parser.summary))
        return 0

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "parse", help=_("parse stdin with the specified parser"),
            # TRANSLATORS: please keep plainbox.parsers untranslated.
            description=_("""
            This command can be used to invoke any of the parsers exposed
            to the `plainbox.parsers` entry point, parse standard input and
            produce a JSON dump of the resulting data structure on stdout.

            Keep in mind that most parsers were designed with the 'C' locale in
            mind. You may have to override the environment variable LANG to
            "C".
            """),
            epilog=(_("Example: ")
                    + "LANG=C pactl list | plainbox dev parse pactl-list"),
        )
        parser.set_defaults(command=self)
        parser.add_argument(
            "parser_name", metavar=_("PARSER-NAME"),
            choices=['?'] + list(self.parser_collection.get_all_names()),
            help=_("Name of the parser to use"))
