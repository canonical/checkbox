# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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
checkbox_support.tests.test_vendor_beacontools_scanner
================================================

Tests for checkbox_support.vendor.beacontools.scanner module
"""

import unittest

from checkbox_support.vendor.beacontools.scanner import HCIVersion


class HCIVersionTests(unittest.TestCase):
    """
    Tests for HCIVersion class
    """

    def test_included(self):
        self.assertEqual(HCIVersion(13), HCIVersion.BT_CORE_SPEC_5_4)

    def test_non_included(self):
        with self.assertRaises(ValueError):
            HCIVersion(-1)
