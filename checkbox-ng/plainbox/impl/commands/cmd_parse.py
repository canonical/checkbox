# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.commands.cmd_parser` -- parser sub-command
==============================================================
"""
from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.parsers import all_parsers


class ParseCommand(PlainBoxCommand):
    """
    Command for running any of the checkbox parsers
    """

    def __init__(self):
        self.parser_collection = all_parsers

    def invoked(self, ns):
        self.parser_collection.load()
        if ns.parser_name == '?':
            return self._print_parser_list()
        else:
            parser = self.parser_collection.get_by_name(ns.parser_name)
            from plainbox.impl.commands.inv_parse import ParseInvocation
            return ParseInvocation(parser).run()

    def _print_parser_list(self):
        print(_("The following parsers are available:"))
        for parser in self.parser_collection.get_all_plugins():
            print("  {}: {}".format(parser.name, parser.summary))
        return 0

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "parse", help=_("parse stdin with the specified parser"),
            prog="plainbox dev parse",
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
        self.parser_collection.load()
        parser.add_argument(
            "parser_name", metavar=_("PARSER-NAME"),
            choices=['?'] + list(self.parser_collection.get_all_names()),
            help=_("Name of the parser to use"))
