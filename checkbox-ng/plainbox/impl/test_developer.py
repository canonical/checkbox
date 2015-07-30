# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

"""Tests for the developer support module."""

import unittest

from plainbox.impl.developer import DeveloperError
from plainbox.impl.developer import UnexpectedMethodCall
from plainbox.impl.developer import UsageExpectation


class _Foo:

    def m1(self):
        UsageExpectation.of(self).enforce()

    def m2(self):
        UsageExpectation.of(self).enforce()


class UnexpectedMethodCallTests(unittest.TestCase):

    """Tests for the UnexpectedMethodCall class."""

    def test_ancestry(self):
        """Check that UnexpectedMethodCall is a subclass of DeveloperError."""
        self.assertTrue(issubclass(UnexpectedMethodCall, DeveloperError))


class UsageExpectationTests(unittest.TestCase):

    """Tests for the UsageExpectation class."""

    def test_of(self):
        """Check that .of() returns the same object for each target."""
        foo1 = _Foo()
        foo2 = _Foo()
        ue1 = UsageExpectation.of(foo1)
        ue2 = UsageExpectation.of(foo2)
        self.assertIsInstance(ue1, UsageExpectation)
        self.assertIsInstance(ue2, UsageExpectation)
        self.assertIs(ue1, UsageExpectation.of(foo1))
        self.assertIs(ue2, UsageExpectation.of(foo2))
        self.assertIsNot(ue1, ue2)

    def test_enforce(self):
        """Check that .enforce() works and produces useful messages."""
        foo = _Foo()
        UsageExpectation.of(foo).allowed_calls = {
            foo.m1: "call m1 now"
        }
        # Nothing should happen here
        foo.m1()
        # Exception should be raised here
        with self.assertRaises(UnexpectedMethodCall) as boom:
            foo.m2()
        self.assertEqual(str(boom.exception), """
Uh, oh...

You are not expected to call _Foo.m2() at this time.

If you see this message then there is a bug somewhere in your code. We are
sorry for this. Perhaps the documentation is flawed, incomplete or confusing.
Please reach out to us if  this happens more often than you'd like.

The set of allowed calls, at this time, is:

 - call _Foo.m1() to call m1 now.

Refer to the documentation of _Foo for details.
    TIP: python -m pydoc plainbox.impl.test_developer._Foo
""")
