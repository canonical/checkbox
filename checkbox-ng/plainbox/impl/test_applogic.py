# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
plainbox.impl.test_applogic
===========================

Test definitions for plainbox.impl.applogic module
"""

from unittest import TestCase

from plainbox.impl.applogic import CompositeQualifier
from plainbox.impl.applogic import IJobQualifier, RegExpJobQualifier
from plainbox.impl.applogic import get_matching_job_list
from plainbox.impl.testing_utils import make_job


class JobQualifierTests(TestCase):

    def test_IJobQualifier_is_abstract(self):
        self.assertRaises(TypeError, IJobQualifier)

    def test_RegExpJobQualifier_smoke(self):
        qualifier = RegExpJobQualifier("foo")
        self.assertEqual(
            repr(qualifier), "<RegExpJobQualifier pattern:'foo'>")
        self.assertTrue(qualifier.designates(make_job("foo")))
        self.assertFalse(qualifier.designates(make_job("bar")))


class CompositeQualifierTests(TestCase):

    def test_empty(self):
        self.assertFalse(
            CompositeQualifier([], []).designates(
                make_job("foo")))

    def test_inclusive(self):
        self.assertTrue(
            CompositeQualifier(
                inclusive_qualifier_list=[RegExpJobQualifier('foo')],
                exclusive_qualifier_list=[]
            ).designates(make_job("foo")))
        self.assertFalse(
            CompositeQualifier(
                inclusive_qualifier_list=[RegExpJobQualifier('foo')],
                exclusive_qualifier_list=[]
            ).designates(make_job("bar")))

    def test_exclusive(self):
        self.assertFalse(
            CompositeQualifier(
                inclusive_qualifier_list=[],
                exclusive_qualifier_list=[RegExpJobQualifier('foo')]
            ).designates(make_job("foo")))
        self.assertFalse(
            CompositeQualifier(
                inclusive_qualifier_list=[RegExpJobQualifier(".*")],
                exclusive_qualifier_list=[RegExpJobQualifier('foo')]
            ).designates(make_job("foo")))
        self.assertTrue(
            CompositeQualifier(
                inclusive_qualifier_list=[RegExpJobQualifier(".*")],
                exclusive_qualifier_list=[RegExpJobQualifier('foo')]
            ).designates(make_job("bar")))


class FunctionTests(TestCase):

    def test_get_matching_job_list(self):
        job_list = [make_job('foo'), make_job('froz'), make_job('barg')]
        self.assertEqual(
            get_matching_job_list(job_list, RegExpJobQualifier('f.*')),
            [make_job('foo'), make_job('froz')])
