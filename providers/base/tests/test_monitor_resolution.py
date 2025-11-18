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
from unittest.mock import patch, MagicMock
from resolution_test import get_gobject_geometry, compare_resolution


class TestMonitorResolution(unittest.TestCase):
    """Test cases for monitor resolution detection."""

    def test_get_gobject_geometry_gtk3(self):
        """Test get_gobject_geometry with GTK3 behavior."""
        # Gtk3 is used for releases below 25
        with patch('resolution_test.release', 24):
            # Mock the display geometry
            mock_geom = MagicMock()
            mock_geom.width = 1920
            mock_geom.height = 1080

            # Mock retrieving geometry from Gdk.Screen
            mock_obj = MagicMock()
            mock_obj.get_monitor_geometry.return_value = mock_geom
            
            # Get width and height from the mocked object
            width, height = get_gobject_geometry(mock_obj, 0)

            # Validate the returned width and height are as expected
            self.assertEqual((width, height), (1920, 1080))

    def test_get_gobject_geometry_gtk4(self):
        """Test get_gobject_geometry with GTK4 behavior."""
        # Gtk4 is used for releases 25 and above
        with patch('resolution_test.release', 25):
            # Mock the display geometry
            mock_geom = MagicMock()
            mock_geom.width = 960
            mock_geom.height = 540
            
            # Mock retrieving geometry from Gdk.Monitor including scale factor
            mock_obj = MagicMock()
            mock_obj.get_geometry.return_value = mock_geom
            mock_obj.get_scale_factor.return_value = 2
            
            # Get width and height from the mocked object
            width, height = get_gobject_geometry(mock_obj)

            # Validate the returned width and height are as expected
            self.assertEqual((width, height), (1920, 1080))

    def test_get_gobject_geometry_fractional_scaling(self):
        """Test get_gobject_geometry with GTK4 behavior with fractional scaling."""
        # Gtk4 is used for releases 25 and above
        with patch('resolution_test.release', 25):
            # Mock the display geometry
            mock_geom = MagicMock()
            mock_geom.width = 1280
            mock_geom.height = 720
            
            # Mock retrieving geometry from Gdk.Monitor including fractional scale factor
            mock_obj = MagicMock()
            mock_obj.get_geometry.return_value = mock_geom
            mock_obj.get_scale_factor.return_value = 1.5
            
            # Get width and height from the mocked object
            width, height = get_gobject_geometry(mock_obj)

            # Validate the returned width and height are as expected
            self.assertEqual((width, height), (1920, 1080))

    def test_compare_resolution_gtk3(self):
        """Test compare_resolution with GTK3 behavior."""
        # Gtk3 is used for releases below 25
        with patch('resolution_test.release', 24):
            with patch('resolution_test.Gdk') as mock_gdk:
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
        with patch('resolution_test.release', 25):
            with patch('resolution_test.Gdk') as mock_gdk:
                # Mock the display geometry
                mock_geom = MagicMock()
                mock_geom.width = 960
                mock_geom.height = 540
                
                # Mock retrieving geometry from Gdk.Monitor
                mock_monitor = MagicMock()
                mock_monitor.get_geometry.return_value = mock_geom
                mock_monitor.get_scale_factor.return_value = 2
                
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

if __name__ == '__main__':
    unittest.main()