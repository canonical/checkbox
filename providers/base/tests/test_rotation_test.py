#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# Written by:
#   Paolo Gentili <paolo.gentili@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import unittest
from unittest.mock import MagicMock, call, patch

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

from rotation_test import main


class TestRotationTest(unittest.TestCase):
    @patch("rotation_test.time.sleep")
    @patch("rotation_test.subprocess.check_call")
    @patch("rotation_test.Gdk")
    def test_main_calls_xrandr_for_all_rotations_and_sleeps(
        self, mock_gdk, mock_check_call, mock_sleep
    ):
        mock_screen = MagicMock()
        mock_screen.get_primary_monitor.return_value = 0
        mock_screen.get_monitor_plug_name.return_value = "HDMI-1"
        mock_gdk.Screen.get_default.return_value = mock_screen

        main()

        expected_calls = [
            call(["xrandr", "--output", "HDMI-1", "--rotation", "right"]),
            call(["xrandr", "--output", "HDMI-1", "--rotation", "inverted"]),
            call(["xrandr", "--output", "HDMI-1", "--rotation", "left"]),
            call(["xrandr", "--output", "HDMI-1", "--rotation", "normal"]),
        ]

        mock_check_call.assert_has_calls(expected_calls)
        mock_sleep.assert_called_with(8)
