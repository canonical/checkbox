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
:mod:`plainbox.impl.test_color`
===============================

Test definitions for plainbox.impl.color
"""

from unittest import TestCase

from plainbox.impl.color import Colorizer
from plainbox.impl.color import ansi_on, ansi_off


class ColorTests(TestCase):

    def test_smoke(self):
        self.assertEqual(ansi_on.f.RED, "\033[31m")
        self.assertEqual(ansi_off.f.RED, "")
        self.assertEqual(ansi_on.b.RED, "\033[41m")
        self.assertEqual(ansi_off.b.RED, "")
        self.assertEqual(ansi_on.s.BRIGHT, "\033[1m")
        self.assertEqual(ansi_off.s.BRIGHT, "")


class ColorizerTests(TestCase):

    def test_is_enabled(self):
        """
        Ensure that .is_enabled reflects the actual colors
        """
        self.assertTrue(Colorizer(True).is_enabled)
        self.assertFalse(Colorizer(False).is_enabled)

    def test_custom(self):
        """
        Ensure that .custom(_) works and obeys color settings
        """
        self.assertEqual(
            Colorizer(False).custom("<text>", "<ansi-code>"), "<text>")
        self.assertEqual(
            Colorizer(True).custom("<text>", "<ansi-code>"),
            "<ansi-code><text>\x1b[0m")
