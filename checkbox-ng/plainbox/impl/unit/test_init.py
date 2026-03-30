# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.unit.test_init
============================

Test definitions for plainbox.impl.unit (package init file)
"""

from unittest import TestCase
from unittest.mock import MagicMock
from textwrap import dedent

from plainbox.impl.unit import get_accessed_parameters, get_array_field_qualify


class GetAccessedParametersTest(TestCase):

    def test_pxu_comptibility(self):
        self.assertEqual(get_accessed_parameters("some text"), frozenset())
        self.assertEqual(
            get_accessed_parameters("some {parametric} text"),
            frozenset(["parametric"]),
        )
        self.assertEqual(
            get_accessed_parameters("some {} text"), frozenset([""])
        )
        self.assertEqual(
            get_accessed_parameters("some {1} {2} {3} text"),
            frozenset(["1", "2", "3"]),
        )

    def test_structured_get_accessed_paramters_list(self):
        self.assertEqual(
            get_accessed_parameters(
                [
                    "no parameters",
                    "some {parameter}",
                    "{multiple} {parameters}",
                ]
            ),
            frozenset(["parameter", "multiple", "parameters"]),
        )

    def test_structured_get_accessed_paramters_dict(self):
        self.assertEqual(
            get_accessed_parameters(
                [
                    "no parameters",
                    {"some {parameter}": {"certification-status": "blocker"}},
                    {
                        "{multiple} {parameters}": {
                            "certification-status": "blocker"
                        }
                    },
                ]
            ),
            frozenset(["parameter", "multiple", "parameters"]),
        )


class GetArrayFieldQualify(TestCase):
    def qualifier(self, s: str):
        s = s.strip()
        if "::" in s:
            return s
        return "com.canonical.certification::" + s

    def test_pxu_comptibility(self):

        self.assertEqual(
            get_array_field_qualify(
                dedent("""
                some
                # some comment
                other
                # some other comment
                com.canonical.plainbox::pre_qualified
                """),
                "include",
                self.qualifier,
                MagicMock(),
            ),
            [
                "com.canonical.certification::some",
                "com.canonical.certification::other",
                "com.canonical.plainbox::pre_qualified",
            ],
        )

    def test_nominal(self):
        self.assertEqual(
            get_array_field_qualify(
                [
                    "some",
                    "other",
                    "com.canonical.plainbox::pre_qualified",
                ],
                "include",
                self.qualifier,
                MagicMock(),
            ),
            [
                "com.canonical.certification::some",
                "com.canonical.certification::other",
                "com.canonical.plainbox::pre_qualified",
            ],
        )
