# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
plainbox.impl.test_depmgr
=========================

Test definitions for plainbox.impl.depmgr module
"""

from unittest import TestCase

from plainbox.impl.depmgr import DependencyCycleError
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.depmgr import DependencyMissingError
from plainbox.impl.depmgr import DependencySolver
from plainbox.impl.testing_utils import make_job


class DependencyCycleErrorTests(TestCase):

    def setUp(self):
        self.A = make_job("A", depends="B")
        self.B = make_job("B", depends="A")
        self.exc = DependencyCycleError([self.A, self.B, self.A])

    def test_job_list(self):
        self.assertEqual(self.exc.job_list, [self.A, self.B, self.A])

    def test_affected_job(self):
        self.assertIs(self.exc.affected_job, self.A)

    def test_affecting_job(self):
        # This is the same as affected_job as this is a cycle
        self.assertIs(self.exc.affecting_job, self.A)

    def test_str(self):
        expected = "dependency cycle detected: A -> B -> A"
        observed = str(self.exc)
        self.assertEqual(expected, observed)

    def test_repr(self):
        expected = ("<DependencyCycleError job_list:["
                    "<JobDefinition name:'A' plugin:'dummy'>, "
                    "<JobDefinition name:'B' plugin:'dummy'>, "
                    "<JobDefinition name:'A' plugin:'dummy'>]>")
        observed = repr(self.exc)
        self.assertEqual(expected, observed)


class DependencyMissingErrorTests(TestCase):

    def setUp(self):
        self.A = make_job("A")
        self.exc_direct = DependencyMissingError(
            self.A, 'B', DependencyMissingError.DEP_TYPE_DIRECT)
        self.exc_resource = DependencyMissingError(
            self.A, 'B', DependencyMissingError.DEP_TYPE_RESOURCE)

    def test_job(self):
        self.assertIs(self.exc_direct.job, self.A)
        self.assertIs(self.exc_resource.job, self.A)

    def test_affected_job(self):
        self.assertIs(self.exc_direct.affected_job, self.A)
        self.assertIs(self.exc_resource.affected_job, self.A)

    def test_affecting_job(self):
        self.assertIs(self.exc_direct.affecting_job, None)
        self.assertIs(self.exc_resource.affecting_job, None)

    def test_missing_job_name(self):
        self.assertEqual(self.exc_direct.missing_job_name, 'B')
        self.assertEqual(self.exc_resource.missing_job_name, 'B')

    def test_str_direct(self):
        expected = "missing dependency: 'B' (direct)"
        observed = str(self.exc_direct)
        self.assertEqual(expected, observed)

    def test_str_resoucee(self):
        expected = "missing dependency: 'B' (resource)"
        observed = str(self.exc_resource)
        self.assertEqual(expected, observed)

    def test_repr_direct(self):
        expected = ("<DependencyMissingError "
                    "job:<JobDefinition name:'A' plugin:'dummy'> "
                    "missing_job_name:'B' "
                    "dep_type:'direct'>")
        observed = repr(self.exc_direct)
        self.assertEqual(expected, observed)

    def test_repr_resource(self):
        expected = ("<DependencyMissingError "
                    "job:<JobDefinition name:'A' plugin:'dummy'> "
                    "missing_job_name:'B' "
                    "dep_type:'resource'>")
        observed = repr(self.exc_resource)
        self.assertEqual(expected, observed)


class DependencyDuplicateErrorTests(TestCase):

    def setUp(self):
        self.A = make_job("A")
        self.another_A = make_job("A")
        self.exc = DependencyDuplicateError(self.A, self.another_A)

    def test_job(self):
        self.assertIs(self.exc.job, self.A)

    def test_duplicate_job(self):
        self.assertIs(self.exc.duplicate_job, self.another_A)

    def test_affected_job(self):
        self.assertIs(self.exc.affected_job, self.A)

    def test_affecting_job(self):
        self.assertIs(self.exc.affecting_job, self.another_A)

    def test_str(self):
        expected = "duplicate job name: 'A'"
        observed = str(self.exc)
        self.assertEqual(expected, observed)

    def test_repr(self):
        expected = ("<DependencyDuplicateError "
                    "job:<JobDefinition name:'A' plugin:'dummy'> "
                    "duplicate_job:<JobDefinition name:'A' plugin:'dummy'>>")
        observed = repr(self.exc)
        self.assertEqual(expected, observed)


class DependencySolverInternalsTests(TestCase):

    def test_get_job_map_produces_map(self):
        A = make_job('A')
        B = make_job('B')
        expected = {'A': A, 'B': B}
        observed = DependencySolver._get_job_map([A, B])
        self.assertEqual(expected, observed)

    def test_get_job_map_find_duplicates(self):
        A = make_job('A')
        another_A = make_job('A')
        with self.assertRaises(DependencyDuplicateError) as call:
            DependencySolver._get_job_map([A, another_A])
        self.assertIs(call.exception.job, A)
        self.assertIs(call.exception.duplicate_job, another_A)


class TestDependencySolver(TestCase):

    def test_empty(self):
        observed = DependencySolver.resolve_dependencies([])
        expected = []
        self.assertEqual(expected, observed)

    def test_direct_deps(self):
        # This tests the following simple job chain
        # A -> B -> C
        A = make_job(name='A', depends='B')
        B = make_job(name='B', depends='C')
        C = make_job(name='C')
        job_list = [A, B, C]
        expected = [C, B, A]
        observed = DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(expected, observed)

    def test_independent_groups_deps(self):
        # This tests two independent job chains
        # A1 -> B1
        # A2 -> B2
        A1 = make_job(name='A1', depends='B1')
        B1 = make_job(name='B1',)
        A2 = make_job(name='A2', depends='B2')
        B2 = make_job(name='B2')
        job_list = [A1, B1, A2, B2]
        expected = [B1, A1, B2, A2]
        observed = DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(expected, observed)

    def test_visiting_blackend_node(self):
        # This tests a visit to already visited job
        # A
        # B -> A
        # A will be visited twice
        A = make_job(name='A')
        B = make_job(name='B', depends='A')
        job_list = [A, B]
        expected = [A, B]
        observed = DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(expected, observed)

    def test_resource_deps(self):
        # This tests resource deps
        # A ~> R
        A = make_job(name='A', requires='R.foo == "bar"')
        R = make_job(name='R', plugin='resource')
        job_list = [A, R]
        expected = [R, A]
        observed = DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(expected, observed)

    def test_duplicate_error(self):
        A = make_job('A')
        another_A = make_job('A')
        job_list = [A, another_A]
        with self.assertRaises(DependencyDuplicateError) as call:
            DependencySolver.resolve_dependencies(job_list)
        self.assertIs(call.exception.job, A)
        self.assertIs(call.exception.duplicate_job, another_A)


    def test_missing_direct_dependency(self):
        # This tests missing dependencies
        # A -> (inexisting B)
        A = make_job(name='A', depends='B')
        job_list = [A]
        with self.assertRaises(DependencyMissingError) as call:
            DependencySolver.resolve_dependencies(job_list)
        self.assertIs(call.exception.job, A)
        self.assertEqual(call.exception.missing_job_name, 'B')
        self.assertEqual(call.exception.dep_type,
                         call.exception.DEP_TYPE_DIRECT)

    def test_missing_resource_dependency(self):
        # This tests missing resource dependencies
        # A ~> (inexisting R)
        A = make_job(name='A', requires='R.attr == "value"')
        job_list = [A]
        with self.assertRaises(DependencyMissingError) as call:
            DependencySolver.resolve_dependencies(job_list)
        self.assertIs(call.exception.job, A)
        self.assertEqual(call.exception.missing_job_name, 'R')
        self.assertEqual(call.exception.dep_type,
                         call.exception.DEP_TYPE_RESOURCE)

    def test_dependency_cycle_self(self):
        # This tests dependency loops
        # A -> A
        A = make_job(name='A', depends='A')
        job_list = [A]
        with self.assertRaises(DependencyCycleError) as call:
            DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(call.exception.job_list, [A, A])

    def test_dependency_cycle_simple(self):
        # This tests dependency loops
        # A -> B -> A
        A = make_job(name='A', depends='B')
        B = make_job(name='B', depends='A')
        job_list = [A, B]
        with self.assertRaises(DependencyCycleError) as call:
            DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(call.exception.job_list, [A, B, A])

    def test_dependency_cycle_longer(self):
        # This tests dependency loops
        # A -> B -> C -> D -> B
        A = make_job(name='A', depends='B')
        B = make_job(name='B', depends='C')
        C = make_job(name='C', depends='D')
        D = make_job(name='D', depends='B')
        job_list = [A, B, C, D]
        with self.assertRaises(DependencyCycleError) as call:
            DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(call.exception.job_list, [B, C, D, B])

    def test_dependency_cycle_via_resource(self):
        # This tests dependency loops
        # A -> R -> A
        A = make_job(name='A', requires='R.key == "value"')
        R = make_job(name='R', depends='A', plugin="resource")
        job_list = [A, R]
        with self.assertRaises(DependencyCycleError) as call:
            DependencySolver.resolve_dependencies(job_list)
        self.assertEqual(call.exception.job_list, [A, R, A])
