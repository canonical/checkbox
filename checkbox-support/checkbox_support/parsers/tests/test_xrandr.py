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

from checkbox_support.parsers.xrandr import parse_xrandr_output, Mode


class TestXRandrParser(unittest.TestCase):

    def test_single_output_with_modes(self):
        output = """
        eDP-1 connected primary 1920x1080+0+0 (normal inverted ) 344mm x 194mm
           1920x1080    144.00*+ 60.00  
           1680x1050    144.00 
        """
        expected = {
            "eDP-1": [
                Mode("1920x1080", 144.00, True, True),
                Mode("1920x1080", 60.00, False, False),
                Mode("1680x1050", 144.00, False, False),
            ]
        }
        self.assertEqual(parse_xrandr_output(output), expected)

    def test_multiple_outputs(self):
        output = """
        HDMI-1 disconnected
        DP-1 connected
           2560x1440    59.95*+
           2048x1152    59.90
        """
        expected = {
            "DP-1": [
                Mode("2560x1440", 59.95, True, True),
                Mode("2048x1152", 59.90, False, False),
            ]
        }
        self.assertEqual(parse_xrandr_output(output), expected)

    def test_empty_input(self):
        output = ""
        expected = {}
        self.assertEqual(parse_xrandr_output(output), expected)

    def test_no_mode_line(self):
        output = """
        DP-2 disconnected
        """
        expected = {}
        self.assertEqual(parse_xrandr_output(output), expected)

    def test_output_with_special_characters(self):
        output = """
        HDMI-2@1 connected
           1920x1200    60.00*+
           1024x768     60.00
        """
        expected = {
            "HDMI-2@1": [
                Mode("1920x1200", 60.00, True, True),
                Mode("1024x768", 60.00, False, False),
            ]
        }
        self.assertEqual(parse_xrandr_output(output), expected)

    def test_modes_with_unexpected_formatting(self):
        output = """
        DP-4 connected
            1920x1080      60.00*+ 50.00 50.00
        """
        expected = {
            "DP-4": [
                Mode("1920x1080", 60.00, True, True),
                Mode("1920x1080", 50.00, False, False),
                Mode("1920x1080", 50.00, False, False),
            ]
        }
        self.assertEqual(parse_xrandr_output(output), expected)

    def test_malformed_lines_ignored(self):
        output = """
        VGA-1 connected
           1024x768     60.00
           Garbled Text Here
           800x600      60.32
        """
        expected = {
            "VGA-1": [
                Mode("1024x768", 60.00, False, False),
                Mode("800x600", 60.32, False, False),
            ]
        }
        self.assertEqual(parse_xrandr_output(output), expected)
