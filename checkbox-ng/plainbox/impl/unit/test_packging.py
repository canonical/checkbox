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
from plainbox.impl.unit.packaging import _strategy_id
from plainbox.impl.unit.packaging import _strategy_id_like
from plainbox.impl.unit.packaging import _strategy_id_version


class DebianPackagingDriverTests(TestCase):

    """Tests for the DebianPackagingDriver class."""

    DEBIAN_JESSIE = {
        'PRETTY_NAME': "Debian GNU/Linux 8 (jessie)",
        'NAME': "Debian GNU/Linux",
        'VERSION_ID': "8",
        'VERSION': "8 (jessie)",
        'ID': 'debian',
        'HOME_URL': "http://www.debian.org/",
        'SUPPORT_URL': "http://www.debian.org/support/",
        'BUG_REPORT_URL': "https://bugs.debian.org/",
    }

    DEBIAN_SID = {
        'PRETTY_NAME': "Debian GNU/Linux stretch/sid",
        'NAME': "Debian GNU/Linux",
        'ID': 'debian',
        'HOME_URL': "https://www.debian.org/",
        'SUPPORT_URL': "https://www.debian.org/support/",
        'BUG_REPORT_URL': "https://bugs.debian.org/",
    }

    UBUNTU_VIVID = {
        'NAME': "Ubuntu",
        'VERSION': "15.04 (Vivid Vervet)",
        'ID': 'ubuntu',
        'ID_LIKE': 'debian',
        'PRETTY_NAME': "Ubuntu 15.04",
        'VERSION_ID': "15.04",
        'HOME_URL': "http://www.ubuntu.com/",
        'SUPPORT_URL': "http://help.ubuntu.com/",
        'BUG_REPORT_URL': "http://bugs.launchpad.net/ubuntu/",
    }

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

    def test_fix_1477095(self):
        """Check https://bugs.launchpad.net/plainbox/+bug/1477095."""
        # This unit is supposed to for Debian (any version) and derivatives.
        # Note below that id match lets both Debian Jessie and Debian Sid pass
        # and that id_like match also lets Ubuntu Vivid pass.
        unit = PackagingMetaDataUnit({
            'os-id': 'debian',
        })
        # Using id and version match
        self.assertFalse(_strategy_id_version(unit, {}))
        self.assertFalse(_strategy_id_version(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id_version(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id_version(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_strategy_id(unit, {}))
        self.assertTrue(_strategy_id(unit, self.DEBIAN_SID))
        self.assertTrue(_strategy_id(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_strategy_id_like(unit, {}))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_JESSIE))
        self.assertTrue(_strategy_id_like(unit, self.UBUNTU_VIVID))
        # This unit is supposed to for Debian Jessie only.  Note below that
        # only Debian Jessie is passed and only by id and version match.
        # Nothing else is allowed.
        unit = PackagingMetaDataUnit({
            'os-id': 'debian',
            'os-version-id': '8'
        })
        # Using id and version match
        self.assertFalse(_strategy_id_version(unit, {}))
        self.assertFalse(_strategy_id_version(unit, self.DEBIAN_SID))
        self.assertTrue(_strategy_id_version(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id_version(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_strategy_id(unit, {}))
        self.assertFalse(_strategy_id(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_strategy_id_like(unit, {}))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id_like(unit, self.UBUNTU_VIVID))
        # This unit is supposed to for Ubuntu (any version) and derivatives.
        # Note that None of the Debian versions pass anymore and the only
        # version that is allowed here is the one Vivid version we test for.
        # (If there was an Elementary test here it would have passed as well, I
        # hope).
        unit = PackagingMetaDataUnit({
            'os-id': 'ubuntu',
        })
        # Using id and version match
        self.assertFalse(_strategy_id_version(unit, {}))
        self.assertFalse(_strategy_id_version(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id_version(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id_version(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_strategy_id(unit, {}))
        self.assertFalse(_strategy_id(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id(unit, self.DEBIAN_JESSIE))
        self.assertTrue(_strategy_id(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_strategy_id_like(unit, {}))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id_like(unit, self.UBUNTU_VIVID))
        # This unit is supposed to for Ubuntu Vivid only.  Note that it behaves
        # exactly like the Debian Jessie test above.  Only Ubuntu Vivid is
        # passed and only by the id and version match.
        unit = PackagingMetaDataUnit({
            'os-id': 'ubuntu',
            'os-version-id': '15.04'
        })
        # Using id and version match
        self.assertFalse(_strategy_id_version(unit, {}))
        self.assertFalse(_strategy_id_version(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id_version(unit, self.DEBIAN_JESSIE))
        self.assertTrue(_strategy_id_version(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_strategy_id(unit, {}))
        self.assertFalse(_strategy_id(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_strategy_id_like(unit, {}))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_SID))
        self.assertFalse(_strategy_id_like(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_strategy_id_like(unit, self.UBUNTU_VIVID))
