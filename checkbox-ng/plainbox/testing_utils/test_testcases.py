# This file is part of Checkbox.
#
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
plainbox.testing_utils.test_testscases
======================================

Test definitions for plainbox.testing_utils.testcases module
"""

from unittest import TestCase, TestResult

from plainbox.testing_utils.testcases import TestCaseParameters
from plainbox.testing_utils.testcases import TestCaseWithParameters


class TestParameterTests(TestCase):

    def test_smoke(self):
        names = ('foo', 'bar')
        values = (1, 2)
        params = TestCaseParameters(names, values)
        self.assertEqual(params.foo, 1)
        self.assertEqual(params.bar, 2)
        with self.assertRaises(AttributeError):
            params.not_there
        self.assertEqual(str(params), "foo: 1, bar: 2")
        self.assertEqual(repr(params), "<TestCaseParameters foo: 1, bar: 2>")

    def test_eq(self):
        # Equal names and values
        self.assertEqual(TestCaseParameters(('a', 'b'), (1, 2)),
                         TestCaseParameters(('a', 'b'), (1, 2)))
        # Different values
        self.assertNotEqual(TestCaseParameters(('a', 'b'), (1, 2)),
                            TestCaseParameters(('a', 'c'), (1, 2)))
        # Different names
        self.assertNotEqual(TestCaseParameters(('a', 'b'), (1, 2)),
                            TestCaseParameters(('a', 'b'), (1, 3)))


class TestCaseWithParametersTests(TestCase):

    class UpperTests(TestCaseWithParameters):

        parameter_names = ('original', 'upper')

        parameter_values = (
            ('lower', 'LOWER'),
            ('typo', 'TYPo'),  # broken on purpose
            ('mIxEd CaSe', 'MIXED CASE'),
        )

        def test_str_upper(self):
            self.assertEqual(
                self.parameters.original.upper(),
                self.parameters.upper)

    def setUp(self):
        self.test_case = self.UpperTests('test_str_upper')
        self.parametrized_test_case = self.test_case._parametrize(
            TestCaseParameters(
                self.UpperTests.parameter_names,
                ('foo', 'FOO')))

    def test_smoke(self):
        result = TestResult()
        self.test_case.run(result)
        # There were no errors (syntax errors and other such stuff)
        self.assertEqual(len(result.errors), 0)
        # There was one test failure
        self.assertEqual(len(result.failures), 1)
        failing_test_case, traceback = result.failures[0]
        # The test case that failed is an instance of what was being tested
        self.assertIsInstance(failing_test_case, self.UpperTests)
        # But they are not the same instance anymore
        self.assertIsNot(failing_test_case, self.test_case)
        # Because the parameters were preserved
        self.assertEqual(failing_test_case.parameters.original, "typo")

    def test_countTestCases(self):
        # There are three parameter values
        self.assertEqual(self.test_case.countTestCases(), 3)
        # This test is parametrized so it counts as only one
        self.assertEqual(self.parametrized_test_case.countTestCases(), 1)

    def test_id(self):
        self.assertIn(
            "test_str_upper [<unparameterized>]",
             self.test_case.id())
        self.assertIn(
            "test_str_upper [original: foo, upper: FOO]",
            self.parametrized_test_case.id())

    def test_str(self):
        self.assertIn(
            "[<unparameterized>]",  str(self.test_case))
        self.assertIn(
            "[original: foo, upper: FOO]", str(self.parametrized_test_case))

    def test_repr(self):
        self.assertIn(
            "parameters=None>", repr(self.test_case))
        self.assertIn(
            "parameters=<TestCaseParameters original: foo, upper: FOO>>",
            repr(self.parametrized_test_case))

    def test_eq(self):
        self.assertEqual(self.test_case, self.test_case)
        self.assertNotEqual(self.test_case, self.parametrized_test_case)
        self.assertNotEqual(self.test_case, 'foo')

    def test_hash(self):
        case1 = TestCaseWithParameters()
        case2 = TestCaseWithParameters()
        self.assertEqual(hash(case1), hash(case2))
        case1_param = case1._parametrize(
            TestCaseParameters(('name', ), ('value', )))
        self.assertNotEqual(case1, case1_param)

    def test_run_spots_common_mistake(self):
        with self.assertRaises(RuntimeError) as boom:
            class UpperTests(TestCaseWithParameters):
                parameter_names = ('param1',)
                parameter_values = (('value1', 'value2'),)
            UpperTests().run()
        self.assertEqual(
            str(boom.exception),
            ("incorrect get_parameter_values() or parameter_values for"
             " iteration 0. Expected to see 1 item but saw 2 instead"))
