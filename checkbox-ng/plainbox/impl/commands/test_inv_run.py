# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
plainbox.impl.commands.test_inv_run
===============================

Test definitions for plainbox.impl.commands.inv_run module
"""

from unittest import TestCase

from plainbox.impl.commands.inv_run import seconds_to_human_duration


class SecondsToHumanDurationTests(TestCase):
    def test_smoke(self):
        self.assertEqual(seconds_to_human_duration(0), "0:00:00")
        self.assertEqual(seconds_to_human_duration(42), "0:00:42")
        self.assertEqual(seconds_to_human_duration(3661), "1:01:01")

    def test_fractions_rounded(self):
        self.assertEqual(seconds_to_human_duration(42.42), "0:00:42")
        self.assertEqual(seconds_to_human_duration(42.6), "0:00:43")
