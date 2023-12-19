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
from unittest.mock import mock_open, patch

from checkbox_ng.app_context import application_name, on_core


class OnCoreTests(TestCase):
    def test_really_on_core(self):
        on_core.cache_clear()
        the_mock = mock_open(read_data="NAME=Ubuntu Core")

        with patch("builtins.open", the_mock):
            self.assertEqual(on_core(), True)

    def test_not_on_core(self):
        on_core.cache_clear()
        the_mock = mock_open(read_data="NAME=Ubuntu")

        with patch("builtins.open", the_mock):
            self.assertEqual(on_core(), False)

    def test_really_on_core_second_line(self):
        on_core.cache_clear()
        the_mock = mock_open(read_data="foobar\nNAME=Ubuntu Core")

        with patch("builtins.open", the_mock):
            self.assertEqual(on_core(), True)

    def test_not_on_core_empty_os_release(self):
        on_core.cache_clear()
        the_mock = mock_open(read_data="")

        with patch("builtins.open", the_mock):
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
