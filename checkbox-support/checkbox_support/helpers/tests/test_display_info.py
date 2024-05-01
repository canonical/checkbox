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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.import unittest

import os
import unittest

from unittest.mock import patch

from checkbox_support.helpers.display_info import get_display_modes


class TestDisplayInfo(unittest.TestCase):

    @patch("checkbox_support.helpers.display_info.parse_gnome_randr_output")
    @patch("os.getenv")
    @patch("subprocess.check_output", return_value="WayWayland")
    def test_get_display_modes_wayland(
        self, mock_check_output, mock_getenv, mock_parse_gnome_randr_output
    ):
        mock_getenv.return_value = "wayland"
        get_display_modes()
        mock_check_output.assert_called_with(["gnome-randr"])
        mock_parse_gnome_randr_output.assert_called_with("WayWayland")

    @patch("checkbox_support.helpers.display_info.parse_xrandr_output")
    @patch("os.getenv")
    @patch("subprocess.check_output", return_value="Xorgz")
    def test_get_display_modes_x11(
        self, mock_check_output, mock_getenv, mock_parse_xrandr_output
    ):
        mock_getenv.return_value = "x11"
        get_display_modes()
        mock_check_output.assert_called_with(["xrandr"])
        mock_parse_xrandr_output.assert_called_with("Xorgz")
