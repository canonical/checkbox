# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
plainbox.impl.unit.test_setup_job
=================================

Test definitions for plainbox.impl.unit.setup_job module
"""

from unittest import TestCase
from unittest.mock import MagicMock

from plainbox.impl.unit.setup_job import RequiredManifest
from plainbox.impl.unit.setup_job import SetupJobUnit
from plainbox.impl.unit.setup_job import valid_requires_manifest


class ValidRequiresManifestTests(TestCase):

    def test_none_is_valid(self):
        self.assertTrue(valid_requires_manifest(None, None))

    def test_string_is_invalid(self):
        self.assertFalse(valid_requires_manifest("manifest-id", None))

    def test_list_of_strings_is_valid(self):
        self.assertTrue(
            valid_requires_manifest(["manifest-id", "other-manifest-id"], None)
        )

    def test_list_of_single_item_dicts_is_valid(self):
        self.assertTrue(
            valid_requires_manifest(
                [
                    {"manifest-id": True},
                    {"other-manifest-id": "value"},
                ],
                None,
            )
        )


class SetupJobUnitTests(TestCase):

    def setUp(self):
        self.self_mock = MagicMock()
        self.self_mock._get_required_manifests_spec = (
            lambda manifest_spec: SetupJobUnit._get_required_manifests_spec(
                self.self_mock, manifest_spec
            )
        )
        self.self_mock.qualify_id = lambda manifest_id: manifest_id

    def test_get_required_manifests_spec_string_without_value(self):
        self.self_mock.requires_manifest = ["manifest-id"]

        self.assertEqual(
            SetupJobUnit.get_required_manifests_spec(self.self_mock),
            [RequiredManifest("manifest-id", True)],
        )

    def test_get_required_manifests_spec_dict_with_one_item(self):
        self.self_mock.requires_manifest = [{"manifest-id": "value"}]

        self.assertEqual(
            SetupJobUnit.get_required_manifests_spec(self.self_mock),
            [RequiredManifest("manifest-id", "value")],
        )
