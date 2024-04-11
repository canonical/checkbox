# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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

"""
plainbox.impl.unit.test_testplan
================================

Test definitions for plainbox.impl.unit.testplan module
"""

from unittest import TestCase
import doctest
import operator

from plainbox.abc import IProvider1
from plainbox.abc import ITextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.qualifiers import OperatorMatcher
from plainbox.impl.secure.qualifiers import PatternMatcher
from plainbox.impl.unit.testplan import TestPlanUnit
from plainbox.impl.unit.testplan import TestPlanUnitSupport
from plainbox.vendor import mock


def load_tests(loader, tests, ignore):
    tests.addTests(
        doctest.DocTestSuite(
            "plainbox.impl.unit.testplan", optionflags=doctest.REPORT_NDIFF
        )
    )
    return tests


class TestTestPlan(TestCase):

    def setUp(self):
        self.provider = mock.Mock(name="provider", spec_set=IProvider1)
        self.provider.namespace = "ns"

    def test_name__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.name, None)

    def test_name__normal(self):
        unit = TestPlanUnit({"name": "name"}, provider=self.provider)
        self.assertEqual(unit.name, "name")

    def test_description__default(self):
        name = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(name.description, None)

    def test_description__normal(self):
        name = TestPlanUnit(
            {"description": "description"}, provider=self.provider
        )
        self.assertEqual(name.description, "description")

    def test_icon__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.icon, None)

    def test_icon__normal(self):
        unit = TestPlanUnit({"icon": "icon"}, provider=self.provider)
        self.assertEqual(unit.icon, "icon")

    def test_include__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.include, None)

    def test_include__normal(self):
        unit = TestPlanUnit({"include": "include"}, provider=self.provider)
        self.assertEqual(unit.include, "include")

    def test_mandatory_include__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.mandatory_include, None)

    def test_mandatory_include__normal(self):
        unit = TestPlanUnit(
            {"mandatory_include": "mandatory_include"}, provider=self.provider
        )
        self.assertEqual(unit.mandatory_include, "mandatory_include")

    def test_bootstrap_include__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.bootstrap_include, None)

    def test_bootstrap_include__normal(self):
        unit = TestPlanUnit(
            {"bootstrap_include": "bootstrap_include"}, provider=self.provider
        )
        self.assertEqual(unit.bootstrap_include, "bootstrap_include")

    def test_exclude__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.exclude, None)

    def test_exclude__normal(self):
        unit = TestPlanUnit({"exclude": "exclude"}, provider=self.provider)
        self.assertEqual(unit.exclude, "exclude")

    def test_category_override__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.category_overrides, None)

    def test_category_override__normal(self):
        unit = TestPlanUnit(
            {
                "category_overrides": "value",
            },
            provider=self.provider,
        )
        self.assertEqual(unit.category_overrides, "value")

    def test_str(self):
        unit = TestPlanUnit({"name": "name"}, provider=self.provider)
        self.assertEqual(str(unit), "name")

    def test_repr(self):
        unit = TestPlanUnit(
            {
                "name": "name",
                "id": "id",
            },
            provider=self.provider,
        )
        self.assertEqual(repr(unit), "<TestPlanUnit id:'ns::id' name:'name'>")

    def test_tr_unit(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.tr_unit(), "test plan")

    def test_estimated_duration__default(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.estimated_duration, None)

    def test_estimated_duration__normal(self):
        self.assertEqual(
            TestPlanUnit({}, provider=self.provider).estimated_duration, None
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "5"}, provider=self.provider
            ).estimated_duration,
            5,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "123.5"}, provider=self.provider
            ).estimated_duration,
            123.5,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "5s"}, provider=self.provider
            ).estimated_duration,
            5,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "1m 5s"}, provider=self.provider
            ).estimated_duration,
            65,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "1h 1m 5s"}, provider=self.provider
            ).estimated_duration,
            3665,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "1h"}, provider=self.provider
            ).estimated_duration,
            3600,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "2m"}, provider=self.provider
            ).estimated_duration,
            120,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "1h 1s"}, provider=self.provider
            ).estimated_duration,
            3601,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "1m:5s"}, provider=self.provider
            ).estimated_duration,
            65,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "1h:1m:5s"}, provider=self.provider
            ).estimated_duration,
            3665,
        )
        self.assertEqual(
            TestPlanUnit(
                {"estimated_duration": "1h:1s"}, provider=self.provider
            ).estimated_duration,
            3601,
        )

    def test_estimated_duration__broken(self):
        unit = TestPlanUnit(
            {"estimated_duration": "foo"}, provider=self.provider
        )
        with self.assertRaises(ValueError):
            unit.estimated_duration

    def test_tr_name(self):
        unit = TestPlanUnit({}, provider=self.provider)
        with mock.patch.object(unit, "get_translated_record_value") as mgtrv:
            retval = unit.tr_name()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with("name")
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_tr_description(self):
        unit = TestPlanUnit({}, provider=self.provider)
        with mock.patch.object(unit, "get_translated_record_value") as mgtrv:
            retval = unit.tr_description()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with("description")
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_parse_matchers__with_provider(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(
            list(unit.parse_matchers("foo")),
            [(0, "id", OperatorMatcher(operator.eq, "ns::foo"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("other::bar")),
            [(0, "id", OperatorMatcher(operator.eq, "other::bar"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]")),
            [(0, "id", PatternMatcher("^ns::sd[a-z]$"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]$")),
            [(0, "id", PatternMatcher("^ns::sd[a-z]$"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]")),
            [(0, "id", PatternMatcher("^ns::sd[a-z]$"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]$")),
            [(0, "id", PatternMatcher("^ns::sd[a-z]$"), None)],
        )

    def test_parse_matchers__without_provider(self):
        unit = TestPlanUnit({}, provider=None)
        self.assertEqual(
            list(unit.parse_matchers("foo")),
            [(0, "id", OperatorMatcher(operator.eq, "foo"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("other::bar")),
            [(0, "id", OperatorMatcher(operator.eq, "other::bar"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]")),
            [(0, "id", PatternMatcher("^sd[a-z]$"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]$")),
            [(0, "id", PatternMatcher("^sd[a-z]$"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]")),
            [(0, "id", PatternMatcher("^sd[a-z]$"), None)],
        )
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]$")),
            [(0, "id", PatternMatcher("^sd[a-z]$"), None)],
        )

    def test_get_qualifier__full(self):
        # Let's pretend the unit looks like this:
        # +0 unit: test plan
        # +1 name: An example test plan
        # +2 include:
        # +3 foo
        # +4  # nothing
        # +5  b.*
        # +6 exclude: bar
        # Let's also assume that it is at a +10 offset in the file it comes
        # from so that the first line +0 is actually the 10th Line
        src = mock.Mock(name="source", spec_set=ITextSource)
        origin = Origin(src, 10, 16)
        field_offset_map = {"unit": 0, "name": 1, "include": 3, "exclude": 6}
        unit = TestPlanUnit(
            {
                "unit": "test plan",
                "name": "An example test plan",
                "include": ("foo\n" "# nothing\n" "b.*\n"),
                "exclude": "bar\n",
            },
            provider=self.provider,
            origin=origin,
            field_offset_map=field_offset_map,
        )
        qual_list = unit.get_qualifier().get_primitive_qualifiers()
        self.assertEqual(qual_list[0].field, "id")
        self.assertIsInstance(qual_list[0].matcher, OperatorMatcher)
        self.assertEqual(qual_list[0].matcher.value, "ns::foo")
        self.assertEqual(qual_list[0].origin, Origin(src, 13, 13))
        self.assertEqual(qual_list[0].inclusive, True)
        self.assertEqual(qual_list[1].field, "id")
        self.assertIsInstance(qual_list[1].matcher, PatternMatcher)
        self.assertEqual(qual_list[1].matcher.pattern_text, "^ns::b.*$")
        self.assertEqual(qual_list[1].origin, Origin(src, 15, 15))
        self.assertEqual(qual_list[1].inclusive, True)
        self.assertEqual(qual_list[2].field, "id")
        self.assertIsInstance(qual_list[2].matcher, OperatorMatcher)
        self.assertEqual(qual_list[2].matcher.value, "ns::bar")
        self.assertEqual(qual_list[2].origin, Origin(src, 16, 16))
        self.assertEqual(qual_list[2].inclusive, False)

    def test_get_qualifier__only_comments(self):
        unit = TestPlanUnit({"include": "# nothing\n"}, provider=self.provider)
        self.assertEqual(unit.get_qualifier().get_primitive_qualifiers(), [])

    def test_get_qualifier__empty(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(unit.get_qualifier().get_primitive_qualifiers(), [])

    def test_parse_category_overrides__with_provider(self):
        unit = TestPlanUnit({}, provider=self.provider)
        self.assertEqual(
            unit.parse_category_overrides('apply "wireless" to "wireless/.*"'),
            [(0, "ns::wireless", "^ns::wireless/.*$")],
        )
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "other::wireless" to "wireless/.*"'
            ),
            [(0, "other::wireless", "^ns::wireless/.*$")],
        )
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "wireless" to "other::wireless/.*"'
            ),
            [(0, "ns::wireless", "^other::wireless/.*$")],
        )
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "first::wireless" to "second::wireless/.*"'
            ),
            [(0, "first::wireless", "^second::wireless/.*$")],
        )

    def test_parse_category_overrides__without_provider(self):
        unit = TestPlanUnit({}, provider=None)
        self.assertEqual(
            unit.parse_category_overrides('apply "wireless" to "wireless/.*"'),
            [(0, "wireless", "^wireless/.*$")],
        )
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "other::wireless" to "wireless/.*"'
            ),
            [(0, "other::wireless", "^wireless/.*$")],
        )
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "wireless" to "other::wireless/.*"'
            ),
            [(0, "wireless", "^other::wireless/.*$")],
        )
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "first::wireless" to "second::wireless/.*"'
            ),
            [(0, "first::wireless", "^second::wireless/.*$")],
        )

    def test_parse_category_overrides__errors(self):
        unit = TestPlanUnit({}, provider=self.provider)
        with self.assertRaisesRegex(ValueError, "expected override value"):
            unit.parse_category_overrides("apply")

    def test_get_bootstrap_job_ids__empty(self):
        unit = TestPlanUnit({}, provider=None)
        self.assertEqual(unit.get_bootstrap_job_ids(), list())

    def test_get_bootstrap_job_ids__normal(self):
        unit = TestPlanUnit({"bootstrap_include": "Foo\nBar"}, provider=None)
        self.assertEqual(unit.get_bootstrap_job_ids(), ["Foo", "Bar"])

    def test_get_bootstrap_job_ids__qualified_ids(self):
        unit = TestPlanUnit(
            {"bootstrap_include": "Foo\nBar"}, provider=self.provider
        )
        self.assertEqual(unit.get_bootstrap_job_ids(), ["ns::Foo", "ns::Bar"])


class TestNestedTestPlan(TestCase):

    def setUp(self):
        self.provider1 = mock.Mock(name="provider1", spec_set=IProvider1)
        self.provider1.namespace = "ns1"
        self.provider2 = mock.Mock(name="provider2", spec_set=IProvider1)
        self.provider2.namespace = "ns2"
        self.tp1 = TestPlanUnit(
            {
                "id": "tp1",
                "unit": "test plan",
                "name": "An example test plan 1",
                "include": "Foo",
                "nested_part": "tp2",
            },
            provider=self.provider1,
        )
        self.tp2 = TestPlanUnit(
            {
                "id": "tp2",
                "unit": "test plan",
                "name": "An example test plan 2",
                "include": "Bar",
                "mandatory_include": "Baz",
                "bootstrap_include": "Qux",
            },
            provider=self.provider1,
        )
        self.tp3 = TestPlanUnit(
            {
                "id": "tp3",
                "unit": "test plan",
                "name": "An example test plan 3",
                "include": "# nothing\n",
                "nested_part": "tp2",
                "certification_status_overrides": "apply blocker to Bar",
            },
            provider=self.provider1,
        )
        self.tp4 = TestPlanUnit(
            {
                "id": "tp4",
                "unit": "test plan",
                "name": "An example test plan 4",
                "include": "# nothing\n",
                "nested_part": ("tp2\n" "tp5\n"),
            },
            provider=self.provider1,
        )
        self.tp5 = TestPlanUnit(
            {
                "id": "tp5",
                "unit": "test plan",
                "name": "An example test plan 5",
                "include": "Baz2",
            },
            provider=self.provider1,
        )
        self.tp6 = TestPlanUnit(
            {
                "id": "tp6",
                "unit": "test plan",
                "name": "An example test plan 6",
                "include": "Foo",
                "nested_part": "ns2::tp7",
            },
            provider=self.provider1,
        )
        self.tp7 = TestPlanUnit(
            {
                "id": "tp7",
                "unit": "test plan",
                "name": "An example test plan 7",
                "include": "Bar",
            },
            provider=self.provider2,
        )
        self.provider1.unit_list = []
        self.provider2.unit_list = [self.tp7]
        self.tp7.provider_list = [self.provider1, self.provider2]
        for i in range(1, 7):
            tp = getattr(self, "tp{}".format(i))
            tp.provider_list = [self.provider1, self.provider2]
            self.provider1.unit_list.append(tp)

    def test_nested_tesplan__qualifiers(self):
        qual_list = self.tp1.get_qualifier().get_primitive_qualifiers()
        mandatory_qual_list = (
            self.tp1.get_mandatory_qualifier().get_primitive_qualifiers()
        )
        bootstrap_qual_list = (
            self.tp1.get_bootstrap_qualifier().get_primitive_qualifiers()
        )
        self.assertEqual(qual_list[0].field, "id")
        self.assertIsInstance(qual_list[0].matcher, OperatorMatcher)
        self.assertEqual(qual_list[0].matcher.value, "ns1::Foo")
        self.assertEqual(qual_list[0].inclusive, True)
        self.assertEqual(qual_list[1].field, "id")
        self.assertIsInstance(qual_list[1].matcher, OperatorMatcher)
        self.assertEqual(qual_list[1].matcher.value, "ns1::Qux")
        self.assertEqual(qual_list[1].inclusive, False)
        self.assertEqual(qual_list[2].field, "id")
        self.assertIsInstance(qual_list[2].matcher, OperatorMatcher)
        self.assertEqual(qual_list[2].matcher.value, "ns1::Bar")
        self.assertEqual(qual_list[2].inclusive, True)
        self.assertEqual(mandatory_qual_list[0].field, "id")
        self.assertIsInstance(mandatory_qual_list[0].matcher, OperatorMatcher)
        self.assertEqual(mandatory_qual_list[0].matcher.value, "ns1::Baz")
        self.assertEqual(mandatory_qual_list[0].inclusive, True)
        self.assertEqual(bootstrap_qual_list[0].field, "id")
        self.assertIsInstance(bootstrap_qual_list[0].matcher, OperatorMatcher)
        self.assertEqual(bootstrap_qual_list[0].matcher.value, "ns1::Qux")
        self.assertEqual(bootstrap_qual_list[0].inclusive, True)

    def test_nested_tesplan__certification_status_override(self):
        support = TestPlanUnitSupport(self.tp3)
        self.assertEqual(
            support.override_list,
            [("^ns1::Bar$", [("certification_status", "blocker")])],
        )

    def test_nested_tesplan__multiple_parts(self):
        qual_list = self.tp4.get_qualifier().get_primitive_qualifiers()
        self.assertEqual(qual_list[1].field, "id")
        self.assertIsInstance(qual_list[1].matcher, OperatorMatcher)
        self.assertEqual(qual_list[1].matcher.value, "ns1::Bar")
        self.assertEqual(qual_list[1].inclusive, True)
        self.assertEqual(qual_list[3].field, "id")
        self.assertIsInstance(qual_list[3].matcher, OperatorMatcher)
        self.assertEqual(qual_list[3].matcher.value, "ns1::Baz2")
        self.assertEqual(qual_list[3].inclusive, True)

    def test_nested_tesplan__multiple_namespaces(self):
        qual_list = self.tp6.get_qualifier().get_primitive_qualifiers()
        self.assertEqual(qual_list[0].field, "id")
        self.assertIsInstance(qual_list[0].matcher, OperatorMatcher)
        self.assertEqual(qual_list[0].matcher.value, "ns1::Foo")
        self.assertEqual(qual_list[0].inclusive, True)
        self.assertEqual(qual_list[1].field, "id")
        self.assertIsInstance(qual_list[1].matcher, OperatorMatcher)
        self.assertEqual(qual_list[1].matcher.value, "ns2::Bar")
        self.assertEqual(qual_list[1].inclusive, True)


class TestTestPlanUnitSupport(TestCase):

    def setUp(self):
        self.tp1 = TestPlanUnit(
            {
                "id": "tp1",
                "unit": "test plan",
                "name": "An example test plan 1",
                "bootstrap_include": "bootstrap_job certification_status=blocker",
                "mandatory_include": "mandatory_job certification_status=blocker",
                "include": "job1 certification_status=non-blocker",
            }
        )
        self.tp2 = TestPlanUnit(
            {
                "id": "tp1",
                "unit": "test plan",
                "name": "An example test plan 2",
                "include": "job1        certification_status=blocker",
            }
        )

    def test_inline_override(self):
        support_tp1 = TestPlanUnitSupport(self.tp1)
        support_tp2 = TestPlanUnitSupport(self.tp2)
        self.assertEqual(
            support_tp1.override_list,
            [
                ("^bootstrap_job$", [("certification_status", "blocker")]),
                ("^job1$", [("certification_status", "non-blocker")]),
                ("^mandatory_job$", [("certification_status", "blocker")]),
            ],
        )
        self.assertEqual(
            support_tp2.override_list,
            [
                ("^job1$", [("certification_status", "blocker")]),
            ],
        )
