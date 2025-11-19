#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
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

import unittest
import sys
from unittest.mock import patch, MagicMock

# Mock gi module
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

from resolution_test import (  # noqa: E402
    get_gobject_geometry,
    compare_resolution,
    check_resolution,
)


class TestMonitorResolution(unittest.TestCase):
    """Test cases for monitor resolution detection."""

    def test_get_gobject_geometry_fractional_scaling(self):
        """Test get_gobject_geometry with GTK4 behavior with fractional scaling."""
        # Gtk4 is used for releases 25 and above
        with patch("resolution_test.release", 25):
            # Mock the display geometry
            mock_geom = MagicMock()
            mock_geom.width = 1280
            mock_geom.height = 720

            # Mock retrieving geometry from Gdk.Monitor including fractional scale factor
            mock_obj = MagicMock()
            mock_obj.get_geometry.return_value = mock_geom
            mock_obj.get_scale.return_value = 1.5

            # Get width and height from the mocked object
            width, height = get_gobject_geometry(mock_obj)

            # Validate the returned width and height are as expected
            self.assertEqual((width, height), (1920, 1080))

    def test_compare_resolution_gtk3(self):
        """Test compare_resolution with GTK3 behavior."""
        # Gtk3 is used for releases below 25
        with patch("resolution_test.release", 24):
            with patch("resolution_test.Gdk") as mock_gdk:
                # Mock the display geometry
                mock_geom = MagicMock()
                mock_geom.width = 1024
                mock_geom.height = 768

                # Mock retrieving geometry from Gdk.Screen primary monitor
                mock_screen = MagicMock()
                mock_screen.get_monitor_geometry.return_value = mock_geom
                mock_screen.get_primary_monitor.return_value = 0
                mock_gdk.Screen.get_default.return_value = mock_screen

                # Get the resolution comparison result
                result = compare_resolution(800, 600)

                # Validate that the resolution meets the minimum requirements
                self.assertTrue(result)

    def test_compare_resolution_gtk4_with_scaling(self):
        """Test compare_resolution with GTK4 behavior and scale factor."""
        # Gtk4 is used for releases 25 and above
        with patch("resolution_test.release", 25):
            with patch("resolution_test.Gdk") as mock_gdk:
                # Mock the display geometry
                mock_geom = MagicMock()
                mock_geom.width = 960
                mock_geom.height = 540

                # Mock retrieving geometry from Gdk.Monitor
                mock_monitor = MagicMock()
                mock_monitor.get_geometry.return_value = mock_geom
                mock_monitor.get_scale.return_value = 2

                # Mock retrieving geometry from mocked monitor
                mock_monitors = MagicMock()
                mock_monitors.get_item.return_value = mock_monitor

                # Mock retrieving Gdk.Display and its monitors
                mock_display = MagicMock()
                mock_display.get_monitors.return_value = mock_monitors
                mock_gdk.Display.get_default.return_value = mock_display

                # Get the resolution comparison result
                result = compare_resolution(800, 600)

                # Validate that the resolution meets the minimum requirements when properly scaled
                # Without scaling, the resolution is 960x540 which is below 800x600
                self.assertTrue(result)

    def test_check_resolution_gtk3(self):
        """Test check_resolution with GTK3 behavior."""
        # Gtk3 is used for releases below 25
        with patch("resolution_test.release", 24):
            with patch("resolution_test.Gdk") as mock_gdk:
                with patch("builtins.print") as mock_print:
                    # Mock the display geometry for multiple monitors
                    mock_geom1 = MagicMock()
                    mock_geom1.width = 1920
                    mock_geom1.height = 1080

                    mock_geom2 = MagicMock()
                    mock_geom2.width = 1024
                    mock_geom2.height = 768

                    # Mock retrieving geometry from Gdk.Screen
                    mock_screen = MagicMock()
                    mock_screen.get_n_monitors.return_value = 2
                    mock_screen.get_monitor_geometry.side_effect = [
                        mock_geom1,
                        mock_geom2,
                    ]
                    mock_gdk.Screen.get_default.return_value = mock_screen

                    # Call check_resolution
                    check_resolution()

                    # Validate that print was called with expected output
                    expected_calls = [
                        unittest.mock.call("Monitor 1:"),
                        unittest.mock.call("  1920 x 1080"),
                        unittest.mock.call("Monitor 2:"),
                        unittest.mock.call("  1024 x 768"),
                    ]
                    mock_print.assert_has_calls(expected_calls)

    def test_check_resolution_gtk4(self):
        """Test check_resolution with GTK4 behavior."""
        # Gtk4 is used for releases 25 and above
        with patch("resolution_test.release", 25):
            with patch("resolution_test.Gdk") as mock_gdk:
                with patch("builtins.print") as mock_print:
                    # Mock the display geometry with scaling
                    mock_geom = MagicMock()
                    mock_geom.width = 960
                    mock_geom.height = 540

                    # Mock monitor with scale factor
                    mock_monitor = MagicMock()
                    mock_monitor.get_geometry.return_value = mock_geom
                    mock_monitor.get_scale.return_value = 2

                    # Mock monitors collection
                    mock_monitors = MagicMock()
                    mock_monitors.get_n_items.return_value = 1
                    mock_monitors.get_item.return_value = mock_monitor

                    # Mock display
                    mock_display = MagicMock()
                    mock_display.get_monitors.return_value = mock_monitors
                    mock_gdk.Display.get_default.return_value = mock_display

                    # Call check_resolution
                    check_resolution()

                    # Validate that print was called with expected output
                    expected_calls = [
                        unittest.mock.call(
                            "Resolution is considering the following scale: 2"
                        ),
                        unittest.mock.call("Monitor 1:"),
                        unittest.mock.call("  1920 x 1080"),
                    ]
                    mock_print.assert_has_calls(expected_calls)


if __name__ == "__main__":
    unittest.main()
