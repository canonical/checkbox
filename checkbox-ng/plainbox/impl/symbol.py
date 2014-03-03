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
:mod:`plainbox.impl.symbol` -- Symbol Type
==========================================

Symbols are special values that evaluate back to themselves. They are global,
unlike enumeration values, and are not bound to any container that defined
them. Symbols can be easily converted to strings and back and are a useful way
to store constants for use inside applications or libraries.

Applications can use Symbol class directly or use the SymbolDef helper to
quickly construct symbols without syntax overhead.
"""

__all__ = ['Symbol', 'SymbolDef']

import inspect


class Symbol:
    """
    Symbol type.

    Instances of this class behave as self-interning strings. All instances are
    tracked and at most one instance with a given symbol name can be
    constructed. The name is immutable.
    """

    __symbols = {}

    def __new__(cls, name):
        """
        Create a new symbol instance.

        If the name was already used in another symbol then that object is
        returned directly. If the name was not used before then construct a new
        Symbol instance and return it.
        """
        try:
            return cls.__symbols[name]
        except KeyError:
            symbol = object.__new__(cls)
            cls.__symbols[name] = symbol
            return symbol

    def __init__(self, name):
        """
        Initialize a symbol with the given name
        """
        self._name = name

    @property
    def name(self):
        """
        name of the symbol
        """
        return self._name

    def __str__(self):
        """
        Convert the symbol object to its name
        """
        return self._name

    def __repr__(self):
        """
        Convert the symbol object to its representation in python
        """
        return "{}({!r})".format(self.__class__.__name__, self._name)

    def __eq__(self, other):
        """
        Compare two symbols or a string and a symbol for equality
        """
        if isinstance(other, Symbol):
            return self is other
        elif isinstance(other, str):
            return self._name == other
        else:
            return False

    def __ne__(self, other):
        """
        Compare two symbols or a string and a symbol for inequality
        """
        if isinstance(other, Symbol):
            return self is not other
        elif isinstance(other, str):
            return self._name != other
        else:
            return False

    def __hash__(self):
        """
        Has the name of the symbol
        """
        return hash(self._name)


class SymbolDefNs:
    """
    Internal implementation detail of the symbol module.

    A special namespace used by :class:`SymbolDefMeta` to keep track of names
    that were being accessed. Each accessed name is converted to a
    :class:`Symbol` and added to the nanespace.
    """

    PASSTHRU = frozenset(('__name__', '__qualname__', '__doc__', '__module__'))

    def __init__(self):
        self.data = {}

    def __setitem__(self, name, value):
        if name in self.PASSTHRU:
            self.data[name] = value
        elif isinstance(value, Symbol):
            self.data[name] = value
        elif isinstance(value, str):
            self.data[name] = Symbol(value)
        else:
            raise ValueError("Only Symbol() instances can be assigned here")

    def __getitem__(self, name):
        if name in self.PASSTHRU:
            return self.data[name]
        elif name in self.data:
            return self.data[name]
        elif name == 'Symbol':
            return Symbol
        else:
            symbol = Symbol(name)
            self.data[name] = symbol
            return symbol


class SymbolDefMeta(type):
    """
    Metaclass for :class:`SymbolDef` which helps to construct multiple symbol
    objects easily. Uses :class:`SymbolDefNs` to keep track of all the symbol
    definitions inside the class and convert them to a list of candidate
    symbols to define.
    """

    @classmethod
    def __prepare__(mcls, name, bases, **kwargs):
        return SymbolDefNs()

    def __new__(mcls, name, bases, ns):
        classdict = ns.data
        classdict['get_all_symbols'] = classmethod(mcls.get_all_symbols)
        return type.__new__(mcls, name, bases, classdict)

    # This is inserted via a simple trick because it's very hard to do any
    # normal method definition inside SymbolDef blocks.
    @staticmethod
    def get_all_symbols(cls):
        """
        Get all symbols defined by this symbol definition block
        """
        # NOTE: This feels a bit like Enum and the extra property that it
        # carries which holds all values. I don't know if we should have that
        # as symbols are not 'bound' to any 'container' like enumeration values
        # are.
        return [value for name, kind, defcls, value
                in inspect.classify_class_attrs(cls)
                if name != '__locals__' and kind == 'data'
                and isinstance(value, Symbol)]


class SymbolDef(metaclass=SymbolDefMeta):
    """
    Helper class that allows to easily define symbols.

    All sub-classes of SymbolDef are evaluated specially. Each word used inside
    the class definition becomes a Symbol() instance. In addition explicit
    assignment can create new symbols. This can be used to create symbols with
    value different from their identifiers.
    """
