# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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

"""Unit tests for app_context module."""

from unittest import TestCase
from unittest.mock import patch

from checkbox_ng.app_context import application_name, on_core


class OnCoreTests(TestCase):
    @patch(
        "checkbox_ng.support.snap_utils.system.get_release_file_content",
        return_value='NAME="Ubuntu Core"\nID=ubuntu-core\nVERSION_ID="24"\n',
    )
    def test_really_on_core(self, _):
        on_core.cache_clear()
        self.assertEqual(on_core(), True)

    @patch(
        "checkbox_ng.support.snap_utils.system.get_release_file_content",
        return_value='NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="24.04"\n',
    )
    def test_not_on_core(self, _):
        on_core.cache_clear()
        self.assertEqual(on_core(), False)


class ApplicationNameTests(TestCase):
    def test_snap_name(self):
        with patch.dict("os.environ", {"SNAP_NAME": "checkbox-acme"}):
            self.assertEqual(application_name(), "checkbox-acme")

    def test_snap_name_generic(self):
        with patch.dict("os.environ", {"SNAP_NAME": "checkbox"}):
            self.assertEqual(application_name(), "checkbox")

    def test_deb_package(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(application_name(), "checkbox")
