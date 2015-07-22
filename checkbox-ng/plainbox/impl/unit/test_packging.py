# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

"""Tests for the PackagingMetaDataUnit and friends."""

from unittest import TestCase

from plainbox.impl.unit.packaging import DebianPackagingDriver
from plainbox.impl.unit.packaging import PackagingMetaDataUnit


class DebianPackagingDriverTests(TestCase):

    """Tests for the DebianPackagingDriver class."""

    def test_fix_1476678(self):
        """Check https://bugs.launchpad.net/plainbox/+bug/1476678."""
        driver = DebianPackagingDriver({})
        driver.collect(PackagingMetaDataUnit({
            'Depends': (
                'python3-checkbox-support (>= 0.2),\n'
                'python3 (>= 3.2),\n'),
            'Recommends': (
                'dmidecode,\n'
                'dpkg (>= 1.13),\n'
                'lsb-release,\n'
                'wodim')
        }))
        self.assertEqual(driver._depends, [
            'python3-checkbox-support (>= 0.2)',
            'python3 (>= 3.2)',
        ])
        self.assertEqual(driver._recommends, [
            'dmidecode',
            'dpkg (>= 1.13)',
            'lsb-release',
            'wodim'
        ])
        self.assertEqual(driver._suggests, [])
