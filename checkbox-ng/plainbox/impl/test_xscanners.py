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

from plainbox.impl.xscanners import WordScanner


def load_tests(loader, tests, ignore):
    tests.addTests(
        doctest.DocTestSuite('plainbox.impl.xscanners',
                             optionflags=doctest.REPORT_NDIFF))
    return tests


class WordScannerTests(unittest.TestCase):

    def test_comments_newline1(self):
        self.assertEqual(
            WordScanner('# comment\n').get_token(),
            (WordScanner.TokenEnum.EOF, ''))

    def test_comments_newline2(self):
        scanner = WordScanner('before# comment\nafter')
        self.assertEqual(
            scanner.get_token(),
            (WordScanner.TokenEnum.WORD, 'before'))
        self.assertEqual(
            scanner.get_token(),
            (WordScanner.TokenEnum.WORD, 'after'))
        self.assertEqual(
            scanner.get_token(),
            (WordScanner.TokenEnum.EOF, ''))

    def test_comments_eof(self):
        scanner = WordScanner('# comment')
        self.assertEqual(
            scanner.get_token(),
            (WordScanner.TokenEnum.EOF, ''))
