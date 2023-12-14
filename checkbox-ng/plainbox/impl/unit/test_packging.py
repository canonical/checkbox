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
import textwrap

from plainbox.impl.unit.packaging import DebianPackagingDriver
from plainbox.impl.unit.packaging import PackagingMetaDataUnit
from plainbox.impl.unit.packaging import _is_id_match
from plainbox.impl.unit.packaging import _is_id_like_match
from plainbox.impl.unit.packaging import _is_id_version_match
from plainbox.impl.unit.packaging import _compare_versions
from plainbox.impl.secure.rfc822 import load_rfc822_records


class DebianPackagingDriverTests(TestCase):

    """Tests for the DebianPackagingDriver class."""

    DEBIAN_JESSIE = {
        "PRETTY_NAME": "Debian GNU/Linux 8 (jessie)",
        "NAME": "Debian GNU/Linux",
        "VERSION_ID": "8",
        "VERSION": "8 (jessie)",
        "ID": "debian",
        "HOME_URL": "http://www.debian.org/",
        "SUPPORT_URL": "http://www.debian.org/support/",
        "BUG_REPORT_URL": "https://bugs.debian.org/",
    }

    DEBIAN_SID = {
        "PRETTY_NAME": "Debian GNU/Linux stretch/sid",
        "NAME": "Debian GNU/Linux",
        "ID": "debian",
        "HOME_URL": "https://www.debian.org/",
        "SUPPORT_URL": "https://www.debian.org/support/",
        "BUG_REPORT_URL": "https://bugs.debian.org/",
    }

    UBUNTU_VIVID = {
        "NAME": "Ubuntu",
        "VERSION": "15.04 (Vivid Vervet)",
        "ID": "ubuntu",
        "ID_LIKE": "debian",
        "PRETTY_NAME": "Ubuntu 15.04",
        "VERSION_ID": "15.04",
        "HOME_URL": "http://www.ubuntu.com/",
        "SUPPORT_URL": "http://help.ubuntu.com/",
        "BUG_REPORT_URL": "http://bugs.launchpad.net/ubuntu/",
    }

    UBUNTU_FOCAL = {
        "NAME": "Ubuntu",
        "ID": "ubuntu",
        "ID_LIKE": "debian",
        "VERSION_ID": "20.04",
    }

    UBUNTU_JAMMY = {
        "NAME": "Ubuntu",
        "ID": "ubuntu",
        "ID_LIKE": "debian",
        "VERSION_ID": "22.04",
    }

    def test_fix_1476678(self):
        """Check https://bugs.launchpad.net/plainbox/+bug/1476678."""
        driver = DebianPackagingDriver({})
        driver.collect(
            PackagingMetaDataUnit(
                {
                    "Depends": (
                        "python3-checkbox-support (>= 0.2),\n"
                        "python3 (>= 3.2),\n"
                    ),
                    "Recommends": (
                        "dmidecode,\n"
                        "dpkg (>= 1.13),\n"
                        "lsb-release,\n"
                        "wodim"
                    ),
                }
            )
        )
        self.assertEqual(
            driver._depends,
            [
                "python3-checkbox-support (>= 0.2)",
                "python3 (>= 3.2)",
            ],
        )
        self.assertEqual(
            driver._recommends,
            ["dmidecode", "dpkg (>= 1.13)", "lsb-release", "wodim"],
        )
        self.assertEqual(driver._suggests, [])

    def test_fix_1477095(self):
        """Check https://bugs.launchpad.net/plainbox/+bug/1477095."""
        # This unit is supposed to for Debian (any version) and derivatives.
        # Note below that id match lets both Debian Jessie and Debian Sid pass
        # and that id_like match also lets Ubuntu Vivid pass.
        unit = PackagingMetaDataUnit(
            {
                "os-id": "debian",
            }
        )
        # Using id and version match
        self.assertFalse(_is_id_version_match(unit, {}))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_version_match(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_is_id_match(unit, {}))
        self.assertTrue(_is_id_match(unit, self.DEBIAN_SID))
        self.assertTrue(_is_id_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_match(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_is_id_like_match(unit, {}))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_JESSIE))
        self.assertTrue(_is_id_like_match(unit, self.UBUNTU_VIVID))
        # This unit is supposed to for Debian Jessie only.  Note below that
        # only Debian Jessie is passed and only by id and version match.
        # Nothing else is allowed.
        unit = PackagingMetaDataUnit({"os-id": "debian", "os-version-id": "8"})
        # Using id and version match
        self.assertFalse(_is_id_version_match(unit, {}))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_SID))
        self.assertTrue(_is_id_version_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_version_match(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_is_id_match(unit, {}))
        self.assertFalse(_is_id_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_match(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_is_id_like_match(unit, {}))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_like_match(unit, self.UBUNTU_VIVID))
        # This unit is supposed to for Ubuntu (any version) and derivatives.
        # Note that None of the Debian versions pass anymore and the only
        # version that is allowed here is the one Vivid version we test for.
        # (If there was an Elementary test here it would have passed as well, I
        # hope).
        unit = PackagingMetaDataUnit(
            {
                "os-id": "ubuntu",
            }
        )
        # Using id and version match
        self.assertFalse(_is_id_version_match(unit, {}))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_version_match(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_is_id_match(unit, {}))
        self.assertFalse(_is_id_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_match(unit, self.DEBIAN_JESSIE))
        self.assertTrue(_is_id_match(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_is_id_like_match(unit, {}))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_like_match(unit, self.UBUNTU_VIVID))
        # This unit is supposed to for Ubuntu Vivid only.  Note that it behaves
        # exactly like the Debian Jessie test above.  Only Ubuntu Vivid is
        # passed and only by the id and version match.
        unit = PackagingMetaDataUnit(
            {"os-id": "ubuntu", "os-version-id": "15.04"}
        )
        # Using id and version match
        self.assertFalse(_is_id_version_match(unit, {}))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_JESSIE))
        self.assertTrue(_is_id_version_match(unit, self.UBUNTU_VIVID))
        # Using id match
        self.assertFalse(_is_id_match(unit, {}))
        self.assertFalse(_is_id_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_match(unit, self.UBUNTU_VIVID))
        # Using id like
        self.assertFalse(_is_id_like_match(unit, {}))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_like_match(unit, self.DEBIAN_JESSIE))
        self.assertFalse(_is_id_like_match(unit, self.UBUNTU_VIVID))

    def test_package_with_comparision(self):
        unit = PackagingMetaDataUnit(
            {"os-id": "ubuntu", "os-version-id": ">=14.04"}
        )
        # Using id and version match
        self.assertFalse(_is_id_version_match(unit, {}))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_SID))
        self.assertFalse(_is_id_version_match(unit, self.DEBIAN_JESSIE))
        self.assertTrue(_is_id_version_match(unit, self.UBUNTU_VIVID))

    def test_read_os_version_from_text(self):
        file_content_1 = textwrap.dedent(
            """\
        unit: packaging meta-data
        os-id: ubuntu
        os-version-id: >=20.04
        Depends: python3-opencv
        """
        )

        record_1 = load_rfc822_records(file_content_1)[0]
        unit_1 = PackagingMetaDataUnit.from_rfc822_record(record_1)

        self.assertFalse(_is_id_version_match(unit_1, self.UBUNTU_VIVID))
        self.assertTrue(_is_id_version_match(unit_1, self.UBUNTU_FOCAL))
        self.assertTrue(_is_id_version_match(unit_1, self.UBUNTU_JAMMY))

        file_content = textwrap.dedent(
            """\
        unit: packaging meta-data
        os-id: ubuntu
        os-version-id: 20.04
        Depends: python3-opencv
        """
        )

        record_2 = load_rfc822_records(file_content)[0]
        unit_2 = PackagingMetaDataUnit.from_rfc822_record(record_2)

        self.assertFalse(_is_id_version_match(unit_2, self.UBUNTU_VIVID))
        self.assertTrue(_is_id_version_match(unit_2, self.UBUNTU_FOCAL))
        self.assertFalse(_is_id_version_match(unit_2, self.UBUNTU_JAMMY))

    def test_compare_versions(self):
        # equal operator
        self.assertTrue(_compare_versions("==1.0.0", "1.0.0"))
        self.assertFalse(_compare_versions("==1.0.1", "1.0.0"))

        self.assertTrue(_compare_versions("1.0.0", "1.0.0"))
        self.assertFalse(_compare_versions("1.0.1", "1.0.0"))

        self.assertTrue(_compare_versions("=1.0.0", "1.0.0"))
        self.assertFalse(_compare_versions("=1.0.1", "1.0.0"))

        # greater than operator
        self.assertTrue(_compare_versions(">1.1.9", "1.2.0"))
        self.assertFalse(_compare_versions(">1.0.0", "1.0.0"))

        # greater than or equal operator
        self.assertTrue(_compare_versions(">=1.0.0", "1.0.0"))
        self.assertTrue(_compare_versions(">=1.0.0", "1.1.0"))
        self.assertFalse(_compare_versions(">=1.0.0", "0.9.9"))

        # less than operator
        self.assertTrue(_compare_versions("<1.0.0", "0.9.9"))
        self.assertFalse(_compare_versions("<1.0.0", "1.0.0"))

        # less than or equal operator
        self.assertTrue(_compare_versions("<=1.0.0", "1.0.0"))
        self.assertTrue(_compare_versions("<=1.0.0", "0.9.9"))

        # not equal operator
        self.assertTrue(_compare_versions("!=1.0.0", "1.0.1"))
        self.assertFalse(_compare_versions("!=1.0.0", "1.0.0"))

        with self.assertRaises(ValueError):
            _compare_versions("!!==1.0.0", "1.0.0")
