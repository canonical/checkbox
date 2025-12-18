# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.giardi@canonical.com>
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

from unittest import TestCase
from unittest.mock import patch, mock_open, MagicMock

from checkbox_support.manifest import get_manifest


class TestManifest(TestCase):
    def test_manifest_present(self):
        mock_file = mock_open(
            read_data='{"com.canonical.certification::some": true}'
        )
        with patch("builtins.open", mock_file) as _:
            manifest = get_manifest()
        self.assertTrue(manifest["com.canonical.certification::some"])
        self.assertFalse(manifest["com.canonical.certification::other"])

    @patch("builtins.open", new=MagicMock(side_effect=FileNotFoundError))
    def test_manifest_not_present(self):
        manifest = get_manifest()

        self.assertFalse(manifest["com.canonical.certification::some"])
        self.assertFalse(manifest["com.canonical.certification::other"])
