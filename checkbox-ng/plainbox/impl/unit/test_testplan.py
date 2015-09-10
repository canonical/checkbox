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
from plainbox.vendor import mock


def load_tests(loader, tests, ignore):
    tests.addTests(
        doctest.DocTestSuite('plainbox.impl.unit.testplan',
                             optionflags=doctest.REPORT_NDIFF))
    return tests


class TestTestPlan(TestCase):

    def setUp(self):
        self.provider = mock.Mock(name='provider', spec_set=IProvider1)
        self.provider.namespace = 'ns'

    def test_name__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.name, None)

    def test_name__normal(self):
        unit = TestPlanUnit({
            'name': 'name'
        }, provider=self.provider)
        self.assertEqual(unit.name, "name")

    def test_description__default(self):
        name = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(name.description, None)

    def test_description__normal(self):
        name = TestPlanUnit({
            'description': 'description'
        }, provider=self.provider)
        self.assertEqual(name.description, "description")

    def test_icon__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.icon, None)

    def test_icon__normal(self):
        unit = TestPlanUnit({
            'icon': 'icon'
        }, provider=self.provider)
        self.assertEqual(unit.icon, "icon")

    def test_include__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.include, None)

    def test_include__normal(self):
        unit = TestPlanUnit({
            'include': 'include'
        }, provider=self.provider)
        self.assertEqual(unit.include, "include")

    def test_mandatory_include__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.mandatory_include, None)

    def test_mandatory_include__normal(self):
        unit = TestPlanUnit({
            'mandatory_include': 'mandatory_include'
        }, provider=self.provider)
        self.assertEqual(unit.mandatory_include, "mandatory_include")

    def test_bootstrap_include__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.bootstrap_include, None)

    def test_bootstrap_include__normal(self):
        unit = TestPlanUnit({
            'bootstrap_include': 'bootstrap_include'
        }, provider=self.provider)
        self.assertEqual(unit.bootstrap_include, 'bootstrap_include')

    def test_exclude__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.exclude, None)

    def test_exclude__normal(self):
        unit = TestPlanUnit({
            'exclude': 'exclude'
        }, provider=self.provider)
        self.assertEqual(unit.exclude, "exclude")

    def test_category_override__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.category_overrides, None)

    def test_category_override__normal(self):
        unit = TestPlanUnit({
            'category-overrides': 'value',
        }, provider=self.provider)
        self.assertEqual(unit.category_overrides, 'value')

    def test_str(self):
        unit = TestPlanUnit({
            'name': 'name'
        }, provider=self.provider)
        self.assertEqual(str(unit), "name")

    def test_repr(self):
        unit = TestPlanUnit({
            'name': 'name',
            'id': 'id',
        }, provider=self.provider)
        self.assertEqual(repr(unit), "<TestPlanUnit id:'ns::id' name:'name'>")

    def test_tr_unit(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.tr_unit(), 'test plan')

    def test_estimated_duration__default(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.estimated_duration, None)

    def test_estimated_duration__normal(self):
        unit = TestPlanUnit({
            'estimated_duration': '5'
        }, provider=self.provider)
        self.assertEqual(unit.estimated_duration, 5)

    def test_estimated_duration__broken(self):
        unit = TestPlanUnit({
            'estimated_duration': 'foo'
        }, provider=self.provider)
        with self.assertRaises(ValueError):
            unit.estimated_duration

    def test_tr_name(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        with mock.patch.object(unit, "get_translated_record_value") as mgtrv:
            retval = unit.tr_name()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with('name')
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_tr_description(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        with mock.patch.object(unit, "get_translated_record_value") as mgtrv:
            retval = unit.tr_description()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with('description')
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_parse_matchers__with_provider(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(
            list(unit.parse_matchers("foo")),
            [(0, 'id', OperatorMatcher(operator.eq, 'ns::foo'), None)])
        self.assertEqual(
            list(unit.parse_matchers("other::bar")),
            [(0, 'id', OperatorMatcher(operator.eq, "other::bar"), None)])
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]")),
            [(0, 'id', PatternMatcher("^ns::sd[a-z]$"), None)])
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]$")),
            [(0, 'id', PatternMatcher("^ns::sd[a-z]$"), None)])
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]")),
            [(0, 'id', PatternMatcher("^ns::sd[a-z]$"), None)])
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]$")),
            [(0, 'id', PatternMatcher("^ns::sd[a-z]$"), None)])

    def test_parse_matchers__without_provider(self):
        unit = TestPlanUnit({
        }, provider=None)
        self.assertEqual(
            list(unit.parse_matchers("foo")),
            [(0, 'id', OperatorMatcher(operator.eq, 'foo'), None)])
        self.assertEqual(
            list(unit.parse_matchers("other::bar")),
            [(0, 'id', OperatorMatcher(operator.eq, "other::bar"), None)])
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]")),
            [(0, 'id', PatternMatcher("^sd[a-z]$"), None)])
        self.assertEqual(
            list(unit.parse_matchers("sd[a-z]$")),
            [(0, 'id', PatternMatcher("^sd[a-z]$"), None)])
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]")),
            [(0, 'id', PatternMatcher("^sd[a-z]$"), None)])
        self.assertEqual(
            list(unit.parse_matchers("^sd[a-z]$")),
            [(0, 'id', PatternMatcher("^sd[a-z]$"), None)])

    def test_get_qualifier__full(self):
        # Let's pretend the unit looks like this:
        # +0 unit: test-plan
        # +1 name: An example test plan
        # +2 include:
        # +3 foo
        # +4  # nothing
        # +5  b.*
        # +6 exclude: bar
        # Let's also assume that it is at a +10 offset in the file it comes
        # from so that the first line +0 is actually the 10th Line
        src = mock.Mock(name='source', spec_set=ITextSource)
        origin = Origin(src, 10, 16)
        field_offset_map = {
            'unit': 0,
            'name': 1,
            'include': 3,
            'exclude': 6
        }
        unit = TestPlanUnit({
            'unit': 'test-plan',
            'name': 'An example test plan',
            'include': (
                'foo\n'
                '# nothing\n'
                'b.*\n'
                ),
            'exclude': 'bar\n'
        }, provider=self.provider, origin=origin,
            field_offset_map=field_offset_map)
        qual_list = unit.get_qualifier().get_primitive_qualifiers()
        self.assertEqual(qual_list[0].field, 'id')
        self.assertIsInstance(qual_list[0].matcher, OperatorMatcher)
        self.assertEqual(qual_list[0].matcher.value, 'ns::foo')
        self.assertEqual(qual_list[0].origin, Origin(src, 13, 13))
        self.assertEqual(qual_list[0].inclusive, True)
        self.assertEqual(qual_list[1].field, 'id')
        self.assertIsInstance(qual_list[1].matcher, PatternMatcher)
        self.assertEqual(qual_list[1].matcher.pattern_text, '^ns::b.*$')
        self.assertEqual(qual_list[1].origin, Origin(src, 15, 15))
        self.assertEqual(qual_list[1].inclusive, True)
        self.assertEqual(qual_list[2].field, 'id')
        self.assertIsInstance(qual_list[2].matcher, OperatorMatcher)
        self.assertEqual(qual_list[2].matcher.value, 'ns::bar')
        self.assertEqual(qual_list[2].origin, Origin(src, 16, 16))
        self.assertEqual(qual_list[2].inclusive, False)

    def test_get_qualifier__only_comments(self):
        unit = TestPlanUnit({
            'include': '# nothing\n'
        }, provider=self.provider)
        self.assertEqual(unit.get_qualifier().get_primitive_qualifiers(), [])

    def test_get_qualifier__empty(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(unit.get_qualifier().get_primitive_qualifiers(), [])

    def test_parse_category_overrides__with_provider(self):
        unit = TestPlanUnit({
        }, provider=self.provider)
        self.assertEqual(
            unit.parse_category_overrides('apply "wireless" to "wireless/.*"'),
            [(0, "ns::wireless", "^ns::wireless/.*$")])
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "other::wireless" to "wireless/.*"'),
            [(0, "other::wireless", "^ns::wireless/.*$")])
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "wireless" to "other::wireless/.*"'),
            [(0, "ns::wireless", "^other::wireless/.*$")])
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "first::wireless" to "second::wireless/.*"'),
            [(0, "first::wireless", "^second::wireless/.*$")])

    def test_parse_category_overrides__without_provider(self):
        unit = TestPlanUnit({
        }, provider=None)
        self.assertEqual(
            unit.parse_category_overrides('apply "wireless" to "wireless/.*"'),
            [(0, "wireless", "^wireless/.*$")])
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "other::wireless" to "wireless/.*"'),
            [(0, "other::wireless", "^wireless/.*$")])
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "wireless" to "other::wireless/.*"'),
            [(0, "wireless", "^other::wireless/.*$")])
        self.assertEqual(
            unit.parse_category_overrides(
                'apply "first::wireless" to "second::wireless/.*"'),
            [(0, "first::wireless", "^second::wireless/.*$")])

    def test_parse_category_overrides__errors(self):
        unit = TestPlanUnit({}, provider=self.provider)
        with self.assertRaisesRegex(ValueError, "expected override value"):
            unit.parse_category_overrides('apply')

    def test_get_bootstrap_job_ids__empty(self):
        unit = TestPlanUnit({}, provider=None)
        self.assertEqual(unit.get_bootstrap_job_ids(), set())

    def test_get_bootstrap_job_ids__normal(self):
        unit = TestPlanUnit({
            'bootstrap_include': 'Foo\nBar'
        }, provider=None)
        self.assertEqual(unit.get_bootstrap_job_ids(), set(['Foo', 'Bar']))

    def test_get_bootstrap_job_ids__qualified_ids(self):
        unit = TestPlanUnit({
            'bootstrap_include': 'Foo\nBar'
        }, provider=self.provider)
        self.assertEqual(unit.get_bootstrap_job_ids(),
                         set(['ns::Foo', 'ns::Bar']))
