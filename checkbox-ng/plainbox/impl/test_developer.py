# This file is part of Checkbox.
#
# Copyright 2015-2026 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

from plainbox.impl.developer import UnexpectedMethodCall, UsageExpectation


class _Foo:

    def m1(self):
        UsageExpectation.of(self).enforce(self.m1)

    def m2(self):
        UsageExpectation.of(self).enforce(self.m2)


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

    def test_add_remove(self):
        foo = _Foo()
        ue = UsageExpectation.of(foo)
        ue.allow(foo.m1, foo.m1, "some motivation")
        foo.m1()
        with self.assertRaises(UnexpectedMethodCall):
            foo.m2()
        ue.disallow(foo.m1, foo.m1)
        with self.assertRaises(UnexpectedMethodCall):
            foo.m1()
        ue.allow(foo.m2, foo.m2, "some other motivation")
        foo.m2()
        # m1 allowed, then m1 disallowed them m2 allowed
        self.assertEqual(
            list(ue.history),
            [
                ("_Foo.m1", "allow"),
                ("_Foo.m1", "disallow"),
                ("_Foo.m2", "allow"),
            ],
        )

    def test_add_not_clear(self):
        foo = _Foo()
        ue = UsageExpectation.of(foo)
        ue.allow(foo.m2, foo.m2, "some")
        UsageExpectation.of(foo).allow_all(
            foo.m1, {foo.m1: "call m1 now"}, clear=False
        )
        foo.m1()
        foo.m2()

    def test_enforce(self):
        """Check that .enforce() works and produces useful messages."""
        foo = _Foo()
        ue = UsageExpectation.of(foo)
        ue.allow_all(foo.m1, {foo.m1: "call m1 now"}, clear=True)
        ue.allow(foo.m1, foo.m1, "stack the history")
        # Nothing should happen here
        foo.m1()
        # Exception should be raised here
        with self.assertRaises(UnexpectedMethodCall) as boom:
            foo.m2()
        self.assertEqual(
            str(boom.exception),
            """
Uh, oh...

If you see this message then there is a bug somewhere in Checkbox. We are
sorry for this. Please report this to us.

You are not expected to call _Foo.m2 at this time.
The set of allowed calls, at this time, is:

 - call _Foo.m1() to stack the history.

The last 5 modifications were done by (most recent last):

 - _Foo.m1 (allow_all, clear)
 - _Foo.m1 (allow)
""",
        )
