# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
import doctest
import unittest

from plainbox.impl.xparsers import WordList, Error


def load_tests(loader, tests, ignore):
    tests.addTests(
        doctest.DocTestSuite(
            "plainbox.impl.xparsers", optionflags=doctest.REPORT_NDIFF
        )
    )
    return tests


class WordParserTests(unittest.TestCase):

    def test_no_loop_forever_unterminated_word_parsable_prefix(self):
        """
        This made the parser loop forever because it would fail to parse from
        `"`, accidentally go back to `,` parse `,` correctly and fail again
        on `"` forever
        """
        parsed = WordList.parse(',"a')  # loops forever
        entries = parsed.entries
        self.assertEqual(len(entries), 1)
        self.assertTrue(isinstance(entries[0], Error))

    def test_no_loop_forever_unterminated_word_parsable_prefix_word(self):
        """
        This made the parser loop forever because it would fail to parse from
        `"`, accidentally go back to `1` parse `1` correctly and fail again
        on `"` forever. Only difference with the one above is that is actually
        does parse something, the 1
        """
        parsed = WordList.parse('1 "a')  # loops forever
        entries = parsed.entries
        self.assertEqual(len(entries), 2)
        self.assertTrue(isinstance(entries[1], Error))

    def test_no_crash_unterminated_word_no_prefix(self):
        """
        This made the parser crash because it tried to go back to the state
        before parsing but the boundary check was wrong (there was one more
        state in the stack)
        """
        parsed = WordList.parse('"a')  # crash
        entries = parsed.entries
        self.assertEqual(len(entries), 1)
        self.assertTrue(isinstance(entries[0], Error))
