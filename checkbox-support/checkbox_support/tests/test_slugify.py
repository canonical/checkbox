# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

from checkbox_support.helpers.slugify import slugify


class TestSlugify(TestCase):
    def test_slugify_no_change(self):
        result = slugify("abc123")
        self.assertEqual(result, "abc123")

    def test_slugify_special_chars(self):
        result = slugify("C'était une belle journée !")
        self.assertEqual(result, "C__tait_une_belle_journ_e__")

    def test_slugify_hyphens(self):
        result = slugify("usb-vendor")
        self.assertEqual(result, "usb_vendor")

    def test_slugify_dots(self):
        result = slugify("my.funny.valentine")
        self.assertEqual(result, "my_funny_valentine")

    def test_slugify_string_starting_with_number(self):
        result = slugify("123abc")
        self.assertEqual(result, "_123abc")

    def test_slugify_empty_string(self):
        result = slugify("")
        self.assertEqual(result, "")

    def test_slugify_none(self):
        result = slugify(None)
        self.assertEqual(result, None)
