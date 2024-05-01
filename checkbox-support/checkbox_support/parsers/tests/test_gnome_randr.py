# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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
import unittest

from textwrap import dedent

from checkbox_support.parsers.gnome_randr import parse_gnome_randr_output, Mode


class TestGnomeRandrParser(unittest.TestCase):

    def test_basic_output(self):
        output = dedent(
            """
        DP-1 Dell Monitor XYZ123
          2560x1440@59.951 2560x1440 59.95*+ [x1.00]
          1920x1080@59.940 1920x1080 59.94 [x1.00, x1.25]
        """
        )
        expected = {
            "DP-1 Dell Monitor XYZ123": [
                Mode("2560x1440", 59.95, True, True),
                Mode("1920x1080", 59.94, False, False),
            ]
        }
        self.assertEqual(parse_gnome_randr_output(output), expected)

    def test_multiple_outputs(self):
        output = dedent(
            """
        HDMI-1 Samsung ABC123
          1920x1080@60.000 1920x1080 60.00*+ [x1.00+]
        DP-2 LG Monitor DEF456
          1280x720@60.000 1280x720 60.00 [x1.00]
        """
        )
        expected = {
            "HDMI-1 Samsung ABC123": [Mode("1920x1080", 60.00, True, True)],
            "DP-2 LG Monitor DEF456": [Mode("1280x720", 60.00, False, False)],
        }
        self.assertEqual(parse_gnome_randr_output(output), expected)

    def test_empty_input(self):
        output = ""
        expected = {}
        self.assertEqual(parse_gnome_randr_output(output), expected)

    def test_incorrect_format(self):
        output = dedent(
            """
        DP-1 Corrupted data
          1920x1080@60.000 Not a Mode [x1.00]
        """
        )
        expected = {"DP-1 Corrupted data": []}
        self.assertEqual(parse_gnome_randr_output(output), expected)

    def test_modes_with_varied_refresh_rate_flags(self):
        output = dedent(
            """
        DP-3 Test Monitor ABC123
          1920x1080@60.000 1920x1080 60.00* [x1.00]
          1920x1080@60.000 1920x1080 60.00+ [x1.00]
        """
        )
        expected = {
            "DP-3 Test Monitor ABC123": [
                Mode("1920x1080", 60.00, False, True),
                Mode("1920x1080", 60.00, True, False),
            ]
        }
        self.assertEqual(parse_gnome_randr_output(output), expected)
