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
plainbox.impl.test_signal
=========================

Test definitions for plainbox.impl.signal module
"""

from unittest import TestCase

from plainbox.impl.signal import Signal, remove_signals_listeners


class SignalTests(TestCase):

    def setUp(self):

        class C:

            @Signal.define
            def on_foo(self):
                self.first_responder_called = True

            @Signal.define
            def on_bar(self):
                self.first_responder_called = True

        self.c = C()

    def test_smoke(self):
        self.c.on_foo.connect(lambda: setattr(self, 'signal_called', True))
        self.c.on_foo()
        self.assertEqual(self.c.first_responder_called, True)
        self.assertEqual(self.signal_called, True)

    def test_remove_signals_listeners(self):
        c = self.c

        class R:

            def __init__(self):
                c.on_foo.connect(self._foo)
                c.on_bar.connect(self._bar)
                c.on_bar.connect(self._baz)

            def _foo(self):
                pass

            def _bar(self):
                pass

            def _baz(self):
                pass

        a = R()
        b = R()
        self.assertEqual(len(a.__listeners__), 3)
        self.assertEqual(len(b.__listeners__), 3)
        remove_signals_listeners(a)
        self.assertEqual(len(a.__listeners__), 0)
        self.assertEqual(len(b.__listeners__), 3)
