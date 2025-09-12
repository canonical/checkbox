# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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


from unittest import TestCase

from plainbox.impl.unit.manifest import ManifestEntryUnit


class UnitWithIdFieldValidationTests(TestCase):

    def test_is_hidden(self):
        self.assertTrue(ManifestEntryUnit({"id": "_hidden"}).is_hidden)
        self.assertFalse(ManifestEntryUnit({"id": "visible"}).is_hidden)

    def test_default_prompt(self):
        self.assertTrue(
            ManifestEntryUnit({"value-type": "natural"}).default_prompt()
        )
        self.assertTrue(
            ManifestEntryUnit({"value-type": "bool"}).default_prompt()
        )

    def test_default_value(self):
        self.assertTrue(
            ManifestEntryUnit({"value-type": "natural"}).default_value()
        )
        self.assertTrue(
            ManifestEntryUnit({"value-type": "bool"}).default_value()
        )

    def test_raises_no_hidden_reason(self):
        res = ManifestEntryUnit(
            {
                "id": "_hidden",
                "value-type": "bool",
                "_name": "Hidden manifest",
                "unit": "manifest",
            }
        ).check()
        self.assertEqual(len(res), 1)
        res = res[0]
        self.assertIn("hidden_reason is mandatory", res.message)
