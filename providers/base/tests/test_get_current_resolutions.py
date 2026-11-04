#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

_mock_gi = MagicMock()
sys.modules.setdefault("gi", _mock_gi)
sys.modules.setdefault("gi.repository", _mock_gi.repository)
sys.modules.setdefault("gi.repository.Gio", _mock_gi.repository.Gio)
sys.modules.setdefault("gi.repository.GLib", _mock_gi.repository.GLib)

from get_current_resolutions import main  # noqa: E402


class CurrentResolutionsTests(unittest.TestCase):
    @patch("get_current_resolutions.MonitorConfigGnome")
    @patch("sys.stdout", new_callable=StringIO)
    def test_prints_sorted_by_connector(self, stdout, mock_gnome):
        mock_gnome.return_value.get_current_resolutions.return_value = {
            "eDP-1": "1920x1200",
            "DP-1": "1280x1024",
        }
        main()
        self.assertEqual(
            stdout.getvalue(), "DP-1: 1280x1024\neDP-1: 1920x1200\n"
        )


if __name__ == "__main__":
    unittest.main()
