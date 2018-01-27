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
:mod:`plainbox.impl.commands.inv_parser` -- parser sub-command
==============================================================
"""
import io
import sys

from plainbox.i18n import gettext as _


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
