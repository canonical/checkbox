# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

"""
plainbox.impl.test_init
=======================

Test definitions for plainbox.impl module
"""

from unittest import TestCase

from plainbox.impl import _get_doc_margin


class MiscTests(TestCase):

    def test_get_doc_margin(self):
        self.assertEqual(
            _get_doc_margin(
                "the first line is ignored\n"
                "  subsequent lines"
                "    get counted"
                "  though"),
            2)
        self.assertEqual(
            _get_doc_margin("what if there is no margin?"), 0)
