# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

from plainbox.impl.highlevel import Explorer, PlainBoxObject
from plainbox.impl.unit.template import TemplateUnit


class TestExplorer(TestCase):
    def test_template_to_obj__without_template_id(self):
        template = TemplateUnit(
            {
                "id": "id",
            }
        )
        explorer = Explorer()
        obj = explorer._template_to_obj(template)
        self.assertEqual(obj.name, "id")

    def test_template_to_obj__with_template_id(self):
        template = TemplateUnit(
            {
                "template-id": "template-id",
            }
        )
        explorer = Explorer()
        obj = explorer._template_to_obj(template)
        self.assertEqual(obj.name, "template-id")


class TestPlainBoxObject(TestCase):
    def test_exact_match(self):
        pbo = PlainBoxObject(None, name="com.canonical.certification::abc")
        found = pbo.find_children_by_name(["abc"], exact=True)
        self.assertEqual(list(found.values()), [[]])

        found = pbo.find_children_by_name(
            ["com.canonical.certification::abc"], exact=True
        )
        self.assertEqual(list(found.values()), [[pbo]])

    def test_non_exact_match(self):
        pbo = PlainBoxObject(None, name="com.canonical.certification::abc")
        found = pbo.find_children_by_name(["abc"], exact=False)
        self.assertEqual(list(found.values()), [[pbo]])

        found = pbo.find_children_by_name(
            ["com.canonical.certification::abc"], exact=False
        )
        self.assertEqual(list(found.values()), [[pbo]])

    def test_explore_tree(self):
        target = PlainBoxObject(
            None, name="com.canonical.certification::target"
        )
        target1 = PlainBoxObject(
            None, name="com.canonical.certification::target1"
        )
        sibiling_unrelated = PlainBoxObject(
            None, name="com.canonical.certification::not-target"
        )
        parent = PlainBoxObject(
            None,
            name="com.canonical.certification::parent",
            children=[target, sibiling_unrelated],
        )
        gparent = PlainBoxObject(
            None,
            name="com.canonical.certification::gparent",
            children=[parent, target1],
        )

        found = gparent.find_children_by_name(["target", "target1"])

        self.assertEqual(found["target"], [target])
        self.assertEqual(found["target1"], [target1])
