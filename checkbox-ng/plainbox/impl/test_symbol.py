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
plainbox.impl.test_symbol
=========================

Test definitions for plainbox.impl.symbol module
"""

import unittest

from plainbox.impl.symbol import SymbolDef, Symbol


class SymbolTests(unittest.TestCase):
    """
    Tests for Symbol class
    """

    def test_symbol_str(self):
        """
        verify that str() produces the symbol name
        """
        self.assertEqual(str(Symbol('foo')), 'foo')

    def test_symbol_repr(self):
        """
        verify that repr() produces the symbol object
        """
        self.assertEqual(repr(Symbol('foo')), "Symbol('foo')")

    def test_symbol_hash(self):
        """
        verify that hash() hashes the symbol name
        """
        self.assertEqual(hash(Symbol('foo')), hash('foo'))

    def test_symbol_name(self):
        """
        verify that Symbol.name returns the symbol name
        """
        self.assertEqual(Symbol('foo').name, 'foo')

    def test_symbol_uniqueness(self):
        """
        verify that two symbols with the same name are indeed a single object
        """
        self.assertIs(Symbol('foo'), Symbol('foo'))

    def test_different_symbols_are_not_same(self):
        """
        verify that two symbols with different names are not the same object
        """
        self.assertIsNot(Symbol('foo'), Symbol('bar'))

    def test_symbol_symbol_comparison(self):
        """
        verify that comparing symbols to symbols works
        """
        self.assertEqual(Symbol('foo'), Symbol('foo'))
        self.assertNotEqual(Symbol('foo'), Symbol('bar'))

    def test_symbol_string_comparison(self):
        """
        verify that comparing symbols to strings works
        """
        self.assertEqual(Symbol('foo'), 'foo')
        self.assertNotEqual(Symbol('foo'), 'bar')

    def test_string_symbol_comparison(self):
        """
        verify that comparing strings to symbols works
        """
        self.assertEqual('foo', Symbol('foo'))
        self.assertNotEqual('bar', Symbol('foo'))

    def test_symbol_other_comparison(self):
        """
        verify that comparing symbols to other types (or vice
        versa) is always False
        """
        self.assertFalse(
            Symbol('foo') == 1,
            "Symbol compared equal to integer")
        self.assertFalse(
            1 == Symbol('foo'),
            "integer compared equal to Symbol")
        self.assertTrue(
            Symbol('foo') != 1,
            "Symbol compared unequal to integer")
        self.assertTrue(
            1 != Symbol('foo'),
            "integer compared unequal to Symbol")


class SymbolDefTests(unittest.TestCase):
    """
    Tests for SymbolDef class
    """

    def test_implicit_symbols(self):
        """
        verify that referencing names inside SymbolDef creates symbols
        """
        class S(SymbolDef):
            a
            b
            c
        self.assertIs(S.a, Symbol('a'))
        self.assertIs(S.b, Symbol('b'))
        self.assertIs(S.c, Symbol('c'))

    def test_custom_symbols(self):
        """
        verify that assigning symbols to variables works
        """
        class S(SymbolDef):
            a = Symbol("the-a-symbol")
        self.assertIs(S.a, Symbol('the-a-symbol'))

    def test_custom_string_symbols(self):
        """
        verify that assigning strings to variables creates symbols
        """
        class S(SymbolDef):
            a = "the-a-symbol"
        self.assertIs(S.a, Symbol('the-a-symbol'))

    def test_repeated_symbol(self):
        """
        verify that repeating a symbol doesn't break anything
        """
        class S(SymbolDef):
            a
            a
        self.assertIs(S.a, Symbol('a'))
        self.assertEqual(S.get_all_symbols(), [Symbol('a')])

    def test_invalid_assignment(self):
        """
        verify that assigning other values is rejected
        """
        with self.assertRaises(ValueError) as boom:
            class S(SymbolDef):
                a = 1
        self.assertEqual(
            str(boom.exception),
            "Only Symbol() instances can be assigned here")

    def test_get_all_symbols(self):
        """
        verify that get_all_symbols() works as intended
        """
        class S(SymbolDef):
            a
            b
            c
        self.assertEqual(
            S.get_all_symbols(), [Symbol('a'), Symbol('b'), Symbol('c')])

    def test_allow_outer(self):
        """
        verify that referencing outer names is allowed via allow_outer
        """
        def magic(text):
            return text.upper()

        class S(SymbolDef, allow_outer=['magic']):
            foo = magic('foo')
        self.assertEqual(S.foo, 'FOO')
