# Copyright 2024 Canonical Ltd.
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

from cpuid import cpuid_to_human_friendly

class CpuidTests(unittest.TestCase):
    def test_hygon_dhyana_plus(self):
        self.assertEquals(
            cpuid_to_human_friendly("0x900f22"),
            "Hygon Dhyana Plus"
        )


