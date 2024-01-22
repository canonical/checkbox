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

from plainbox.impl.highlevel import Explorer
from plainbox.impl.unit.template import TemplateUnit


class TestExplorer(TestCase):
    def test_template_to_obj__without_template_id(self):
        template = TemplateUnit({
            "id": "id",
        })
        explorer = Explorer()
        obj = explorer._template_to_obj(template)
        self.assertEqual(obj.name, "id")

    def test_template_to_obj__with_template_id(self):
        template = TemplateUnit({
            "template-id": "template-id",
        })
        explorer = Explorer()
        obj = explorer._template_to_obj(template)
        self.assertEqual(obj.name, "template-id")
