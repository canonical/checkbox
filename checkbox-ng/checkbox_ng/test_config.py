# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
checkbox_ng.test_config
=======================

Test definitions for checkbox_ng.config module
"""

from unittest import TestCase

from plainbox.impl.secure.config import Unset

from checkbox_ng.config import CheckBoxConfig


class PlainBoxConfigTests(TestCase):

    def test_smoke(self):
        config = CheckBoxConfig()
        self.assertIs(config.secure_id, Unset)
        secure_id = "0123456789ABCDE"
        config.secure_id = secure_id
        self.assertEqual(config.secure_id, secure_id)
        with self.assertRaises(ValueError):
            config.secure_id = "bork"
        self.assertEqual(config.secure_id, secure_id)
        del config.secure_id
        self.assertIs(config.secure_id, Unset)
