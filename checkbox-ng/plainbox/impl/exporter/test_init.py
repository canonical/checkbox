# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.exporter.test_init
================================

Test definitions for plainbox.impl.exporter module
"""

from unittest import TestCase

from plainbox.impl.exporter import classproperty


class ClassPropertyTests(TestCase):

    def get_C(self):

        class C:
            attr = "data"

            @classproperty
            def prop(cls):
                return cls.attr

        return C

    def test_classproperty_on_cls(self):
        cls = self.get_C()
        self.assertEqual(cls.prop, cls.attr)

    def test_classproperty_on_obj(self):
        cls = self.get_C()
        obj = cls()
        self.assertEqual(obj.prop, obj.attr)
