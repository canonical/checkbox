# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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

from plainbox.impl.signal import Signal


class SignalTests(TestCase):

    def test_smoke(self):

        class C:

            @Signal.define
            def on_foo(self):
                self.first_responder_called = True

        c = C()
        c.on_foo.connect(lambda: setattr(self, 'signal_called', True))
        c.on_foo()
        self.assertEqual(c.first_responder_called, True)
        self.assertEqual(self.signal_called, True)
