# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
checkbox_support.tests.test_human_readable_bytes
================================================

Tests for checkbox_support.helpers.human_readable_bytes module
"""

import unittest

from checkbox_support.helpers.human_readable_bytes import HumanReadableBytes


class HumanReadableBytesTests(unittest.TestCase):
    """
    Tests for HumanReadableBytesTests class
    """

    def test_parsing_all_equal_four(self):
        fours = [HumanReadableBytes(4), 4, HumanReadableBytes("4"),
                 HumanReadableBytes("4B"), HumanReadableBytes("4b"), int("4")]
        self.assertEqual(all(fours[0] == four for four in fours), True)

    def test_parsin_all_minus_2kibi(self):
        values = [HumanReadableBytes("-2ki"), -2048,
                  HumanReadableBytes("-2048"), HumanReadableBytes("-2KiB")]
        self.assertEqual(all(values[0] == val for val in values), True)

    def test_four_megs(self):
        values = [HumanReadableBytes("4mB"), int("4"+"0"*6),
                  HumanReadableBytes(4000000), 4000000]
        self.assertEqual(all(values[0] == val for val in values), True)

    def test_str(self):
        self.assertEqual(str(HumanReadableBytes("4mi")), "4MiB")

    def test_str_rounding(self):
        self.assertEqual(str(HumanReadableBytes(4*1024*1024+1)), "4.00MiB")

    def test_str_zero(self):
        self.assertEqual(str(HumanReadableBytes("0 MiB")), "0B")

    def test_repr(self):
        self.assertEqual(repr(HumanReadableBytes("5kib")),
                         "HumanReadableBytes(5120)")
