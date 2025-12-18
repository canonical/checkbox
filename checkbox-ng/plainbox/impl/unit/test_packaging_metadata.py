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

from plainbox.impl.unit.packaging_metadata import DebianPackagingDriver
from plainbox.impl.unit.packaging_metadata import PackagingDriverBase
from plainbox.impl.unit.packaging_metadata import PackagingMetaDataUnit
from plainbox.impl.unit.test_unit import UnitFieldValidationTests
from plainbox.impl.unit.validators import UnitValidationContext
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity

from plainbox.impl.secure.rfc822 import load_rfc822_records


class DebianPackagingDriverTests(TestCase):
    """Tests for the DebianPackagingDriver class."""

    empty_driver = DebianPackagingDriver({})
    debian_jessie_driver = DebianPackagingDriver(
        {
            "PRETTY_NAME": "Debian GNU/Linux 8 (jessie)",
            "NAME": "Debian GNU/Linux",
            "VERSION_ID": "8",
            "VERSION": "8 (jessie)",
            "ID": "debian",
            "HOME_URL": "http://www.debian.org/",
            "SUPPORT_URL": "http://www.debian.org/support/",
            "BUG_REPORT_URL": "https://bugs.debian.org/",
        }
    )

    debian_sid_driver = DebianPackagingDriver(
        {
            "PRETTY_NAME": "Debian GNU/Linux stretch/sid",
            "NAME": "Debian GNU/Linux",
            "ID": "debian",
            "HOME_URL": "https://www.debian.org/",
            "SUPPORT_URL": "https://www.debian.org/support/",
            "BUG_REPORT_URL": "https://bugs.debian.org/",
        }
    )

    ubuntu_vivid_driver = DebianPackagingDriver(
        {
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
    )

    ubuntu_focal_driver = DebianPackagingDriver(
        {
            "NAME": "Ubuntu",
            "ID": "ubuntu",
            "ID_LIKE": "debian",
            "VERSION_ID": "20.04",
        }
    )

    ubuntu_jammy_driver = DebianPackagingDriver(
        {
            "NAME": "Ubuntu",
            "ID": "ubuntu",
            "ID_LIKE": "debian",
            "VERSION_ID": "22.04",
        }
    )

    debian_unit = PackagingMetaDataUnit({"os-id": "debian"})
    debian_8_unit = PackagingMetaDataUnit(
        {"os-id": "debian", "os-version-id": "8"}
    )
    ubuntu_unit = PackagingMetaDataUnit({"os-id": "ubuntu"})
    ubuntu_15_unit = PackagingMetaDataUnit(
        {"os-id": "ubuntu", "os-version-id": "15.04"}
    )
    ubuntu_22_unit = PackagingMetaDataUnit(
        {"os-id": "ubuntu", "os-version-id": "22.04"}
    )
    fedora_unit = PackagingMetaDataUnit(
        {"os-id": "fedora", "os-version-id": "33"}
    )

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
            ["python3-checkbox-support (>= 0.2)", "python3 (>= 3.2)"],
        )
        self.assertEqual(
            driver._recommends,
            ["dmidecode", "dpkg (>= 1.13)", "lsb-release", "wodim"],
        )
        self.assertEqual(driver._suggests, [])

    def test_fix_1477095(self):
        """Check https://bugs.launchpad.net/plainbox/+bug/1477095."""

        # This unit should apply for Debian (any version) and derivatives.
        # Note below that id match lets both Debian Jessie and Debian Sid pass
        # and that id_like match also lets Ubuntu Vivid pass.
        unit = self.debian_unit
        self.assertFalse(self.empty_driver.is_applicable(unit))
        self.assertTrue(self.debian_sid_driver.is_applicable(unit))
        self.assertTrue(self.debian_jessie_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_vivid_driver.is_applicable(unit))

        # This unit should apply for Debian Jessie only.  Note below that
        # only Debian Jessie is passed and only by id and version match.
        # Nothing else is allowed.
        unit = self.debian_8_unit
        self.assertFalse(self.empty_driver.is_applicable(unit))
        self.assertFalse(self.debian_sid_driver.is_applicable(unit))
        self.assertTrue(self.debian_jessie_driver.is_applicable(unit))
        self.assertFalse(self.ubuntu_vivid_driver.is_applicable(unit))

        # This unit should apply for Ubuntu (any version) and derivatives.
        # Note that None of the Debian versions pass anymore and the only
        # version that is allowed here is the one Vivid version we test for.
        # (If there was an Elementary test here it would have passed as well, I
        # hope).
        unit = self.ubuntu_unit
        self.assertFalse(self.empty_driver.is_applicable(unit))
        self.assertFalse(self.debian_sid_driver.is_applicable(unit))
        self.assertFalse(self.debian_jessie_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_vivid_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_focal_driver.is_applicable(unit))

        # This unit should apply for Ubuntu Vivid only.  Note that it behaves
        # exactly like the Debian Jessie test above.  Only Ubuntu Vivid is
        # passed and only by the id and version match.
        unit = self.ubuntu_15_unit
        self.assertFalse(self.empty_driver.is_applicable(unit))
        self.assertFalse(self.debian_sid_driver.is_applicable(unit))
        self.assertFalse(self.debian_jessie_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_vivid_driver.is_applicable(unit))
        self.assertFalse(self.ubuntu_focal_driver.is_applicable(unit))

    def test_id_match(self):
        driver = self.ubuntu_jammy_driver
        # It outputs true for the same id and no version is specified
        self.assertTrue(driver._is_id_match(self.ubuntu_unit))
        # It outputs false for different id
        self.assertFalse(driver._is_id_match(self.debian_unit))
        # It outputs false for the same id and some version is specified
        self.assertFalse(driver._is_id_match(self.ubuntu_15_unit))
        # It outputs false with no id
        self.assertFalse(self.empty_driver._is_id_match(self.ubuntu_unit))

    def test_id_like_match(self):
        driver = self.ubuntu_jammy_driver
        # It outputs true for the id_like id and no version is specified
        self.assertTrue(driver._is_id_like_match(self.debian_unit))
        # It outputs false for different id_like id
        self.assertFalse(driver._is_id_like_match(self.fedora_unit))
        # It outputs false for the same id and some version is specified
        self.assertFalse(driver._is_id_like_match(self.debian_8_unit))
        # It outputs false with no id
        self.assertFalse(self.empty_driver._is_id_like_match(self.ubuntu_unit))

    def test_id_version_match(self):
        driver = self.ubuntu_jammy_driver
        # It outputs true for the same id and version
        self.assertTrue(driver._is_id_version_match(self.ubuntu_22_unit))
        # It outputs false for the same id and different version
        self.assertFalse(driver._is_id_version_match(self.ubuntu_15_unit))
        # It outputs false with no version
        self.assertFalse(driver._is_id_version_match(self.ubuntu_unit))

    def test_package_with_comparision(self):
        unit = PackagingMetaDataUnit(
            {"os-id": "ubuntu", "os-version-id": ">=20.04"}
        )
        # Using id and version match
        self.assertTrue(self.ubuntu_jammy_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_focal_driver.is_applicable(unit))
        self.assertFalse(self.ubuntu_vivid_driver.is_applicable(unit))
        self.assertFalse(self.debian_jessie_driver.is_applicable(unit))

    def test_read_os_version_from_text(self):
        file_content = textwrap.dedent(
            """\
        unit: packaging meta-data
        os-id: ubuntu
        os-version-id: >=20.04
        Depends: python3-opencv
        """
        )

        record = load_rfc822_records(file_content)[0]
        unit = PackagingMetaDataUnit.from_rfc822_record(record)

        self.assertFalse(self.ubuntu_vivid_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_focal_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_jammy_driver.is_applicable(unit))

    def test_read_os_version_comparison_from_text(self):
        file_content = textwrap.dedent(
            """\
        unit: packaging meta-data
        os-id: ubuntu
        os-version-id: 20.04
        Depends: python3-opencv
        """
        )

        record = load_rfc822_records(file_content)[0]
        unit = PackagingMetaDataUnit.from_rfc822_record(record)

        self.assertFalse(self.ubuntu_vivid_driver.is_applicable(unit))
        self.assertTrue(self.ubuntu_focal_driver.is_applicable(unit))
        self.assertFalse(self.ubuntu_jammy_driver.is_applicable(unit))

    def test_compare_versions(self):
        compare_versions = PackagingDriverBase._compare_versions
        # equal operator
        self.assertTrue(compare_versions("== 1.0.0", "1.0.0"))
        self.assertFalse(compare_versions("== 1.0.1", "1.0.0"))

        self.assertTrue(compare_versions("1.0.0", "1.0.0"))
        self.assertFalse(compare_versions("1.0.1", "1.0.0"))

        # greater than operator
        self.assertTrue(compare_versions("> 1.1.9", "1.2.0"))
        self.assertFalse(compare_versions("> 1.0.0", "1.0.0"))

        # greater than or equal operator
        self.assertTrue(compare_versions(">= 1.0.0", "1.0.0"))
        self.assertTrue(compare_versions(">= 1.0.0", "1.1.0"))
        self.assertFalse(compare_versions(">= 1.0.0", "0.9.9"))

        # less than operator
        self.assertTrue(compare_versions("< 1.0.0", "0.9.9"))
        self.assertFalse(compare_versions("< 1.0.0", "1.0.0"))

        # less than or equal operator
        self.assertTrue(compare_versions("<= 1.0.0", "1.0.0"))
        self.assertTrue(compare_versions("<= 1.0.0", "0.9.9"))

        # not equal operator
        self.assertTrue(compare_versions("!= 1.0.0", "1.0.1"))
        self.assertFalse(compare_versions("!= 1.0.0", "1.0.0"))

    def test_malformed_versions(self):
        compare_versions = PackagingDriverBase._compare_versions

        # Using just one equal operator
        with self.assertRaises(SystemExit) as context:
            compare_versions("= 1.0.0", "1.0.0")
            self.assertIn("= 1.0.0", str(context.exception))

        # Using a bad operator
        with self.assertRaises(SystemExit) as context:
            compare_versions("!!== 1.0.0", "1.0.0")
            self.assertIn("!! == 1.0.0", str(context.exception))

        # Using composed operators
        with self.assertRaises(SystemExit) as context:
            compare_versions(">=1.0.0, <=2.0.0", "1.0.0")

        # Using wrong version format
        with self.assertRaises(SystemExit) as context:
            compare_versions("== ***", "1.0.0")

    def test_unit_to_string(self):
        unit = PackagingMetaDataUnit(
            {
                "os-id": "ubuntu",
                "os-version-id": "22.04",
                "Depends": "dep_package",
                "Recommends": "rec_package",
                "Suggests": "sug_package",
            }
        )

        unit_string = str(unit)

        self.assertIn("ubuntu", unit_string)
        self.assertIn("Depends: dep_package", unit_string)
        self.assertIn("Recommends: rec_package", unit_string)
        self.assertIn("Suggests: sug_package", unit_string)


class PackagingUnitFieldValidationTests(UnitFieldValidationTests):
    def test_validation_unique_package(self):
        unit_1 = PackagingMetaDataUnit(
            {
                "os-id": "ubuntu",
                "os-version-id": ">=20.04",
                "Depends": "dep_package1",
                "Recommends": "rec_package1",
                "Suggests": "sug_package1",
            },
            provider=self.provider,
        )
        unit_2 = PackagingMetaDataUnit(
            {
                "os-id": "ubuntu",
                "os-version-id": ">=20.04",
                "Depends": "dep_package1",
                "Recommends": "rec_package1",
                "Suggests": "sug_package1",
            },
            provider=self.provider,
        )

        self.provider.unit_list = [unit_1, unit_2]
        self.provider.problem_list = []
        context = UnitValidationContext([self.provider])
        issue_list = unit_1.check(context=context)

        message_start = "field 'Depends', clashes with 1 other unit"
        depends_issue = self.assertIssueFound(
            issue_list,
            PackagingMetaDataUnit.Meta.fields.Depends,
            Problem.not_unique,
            Severity.error,
        )
        self.assertTrue(depends_issue.message.startswith(message_start))

        message_start = "field 'Recommends', clashes with 1 other unit"
        recommends_issue = self.assertIssueFound(
            issue_list,
            PackagingMetaDataUnit.Meta.fields.Recommends,
            Problem.not_unique,
            Severity.error,
        )
        self.assertTrue(recommends_issue.message.startswith(message_start))

        message_start = "field 'Suggests', clashes with 1 other unit"
        suggests_issue = self.assertIssueFound(
            issue_list,
            PackagingMetaDataUnit.Meta.fields.Suggests,
            Problem.not_unique,
            Severity.error,
        )
        self.assertTrue(suggests_issue.message.startswith(message_start))
