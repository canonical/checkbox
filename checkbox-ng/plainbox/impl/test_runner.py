# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_runner
=========================

Test definitions for plainbox.impl.runner module
"""

from unittest import TestCase

from plainbox.impl.runner import slugify


class SlugifyTests(TestCase):

    def test_random_strings(self):
        self.assertEqual(slugify("A "), "A_")
        self.assertEqual(slugify("A-"), "A-")
        self.assertEqual(slugify("A_"), "A_")
        self.assertEqual(slugify(".b"), ".b")
        self.assertEqual(slugify("\z"), "_z")
        self.assertEqual(slugify("/z"), "_z")
        self.assertEqual(slugify("1k"), "1k")
