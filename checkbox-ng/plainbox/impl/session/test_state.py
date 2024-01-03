# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
plainbox.impl.test_session
==========================

Test definitions for plainbox.impl.session module
"""
from doctest import DocTestSuite
from doctest import REPORT_NDIFF
from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.depmgr import DependencyMissingError
from plainbox.impl.depmgr import DependencyUnknownError
from plainbox.impl.resource import Resource
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.qualifiers import JobIdQualifier
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.session import InhibitionCause
from plainbox.impl.session import SessionState
from plainbox.impl.session import UndesiredJobReadinessInhibitor
from plainbox.impl.session.state import SessionDeviceContext
from plainbox.impl.session.state import SessionMetaData
from plainbox.impl.testing_utils import make_job
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.unit import Unit
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.vendor import mock
from plainbox.vendor.morris import SignalTestCase


def load_tests(loader, tests, ignore):
    tests.addTests(DocTestSuite(
        'plainbox.impl.session.state', optionflags=REPORT_NDIFF))
    return tests


class SessionStateSmokeTests(TestCase):

    def setUp(self):
        A = make_job('A', requires='R.attr == "value"')
        B = make_job('B', depends='C')
        C = make_job('C')
        self.job_list = [A, B, C]
        self.session_state = SessionState(self.job_list)

    def test_initial_job_list(self):
        expected = self.job_list
        observed = self.session_state.job_list
        self.assertEqual(expected, observed)

    def test_initial_desired_job_list(self):
        expected = []
        observed = self.session_state.desired_job_list
        self.assertEqual(expected, observed)

    def test_initial_run_list(self):
        expected = []
        observed = self.session_state.run_list
        self.assertEqual(expected, observed)

    def test_update_mandatory_job_list_updates(self):
        D = make_job('D')
        self.session_state.update_mandatory_job_list([D])
        expected = [D]
        observed = self.session_state.mandatory_job_list
        self.assertEqual(expected, observed)


class RegressionTests(TestCase):
    # Tests for bugfixes

    def test_crash_on_missing_job(self):
        """ http://pad.lv/1334296 """
        A = make_job("A")
        state = SessionState([])
        problems = state.update_desired_job_list([A])
        self.assertEqual(problems, [DependencyUnknownError(A)])
        self.assertEqual(state.desired_job_list, [])

    def test_crash_in_update_desired_job_list(self):
        # This checks if a DependencyError can cause crash
        # update_desired_job_list() with a ValueError, in certain conditions.
        A = make_job('A', depends='X')
        L = make_job('L', plugin='shell')
        session = SessionState([A, L])
        problems = session.update_desired_job_list([A, L])
        # We should get exactly one DependencyMissingError related to job A and
        # the undefined job X
        self.assertEqual(len(problems), 1)
        self.assertIsInstance(problems[0], DependencyMissingError)
        self.assertIs(problems[0].affected_job, A)

    def test_init_with_identical_jobs(self):
        A = make_job("A")
        second_A = make_job("A")
        third_A = make_job("A")
        session = SessionState([A, second_A, third_A])
        # But we don't really store both, just the first one
        self.assertEqual(session.job_list, [A])

    def test_init_with_colliding_jobs(self):
        # This is similar to the test above but the jobs actually differ In
        # this case the _second_ job is rejected but it really signifies a
        # deeper problem that should only occur during development of jobs
        A = make_job("A")
        different_A = make_job("A", plugin="resource")
        with self.assertRaises(DependencyDuplicateError) as call:
            SessionState([A, different_A])
            self.assertIs(call.exception.job, A)
            self.assertIs(call.exception.duplicate_job, different_A)
            self.assertIs(call.exception.affected_job, different_A)

    def test_dont_remove_missing_jobs(self):
        """ http://pad.lv/1444126 """
        A = make_job("A", depends="B")
        B = make_job("B", depends="C")
        state = SessionState([A, B])
        problems = state.update_desired_job_list([A, B])
        self.assertEqual(problems, [
            DependencyMissingError(B, 'C', 'direct'),
            DependencyMissingError(A, 'B', 'direct'),
        ])
        self.assertEqual(state.desired_job_list, [])
        self.assertEqual(state.run_list, [])


class SessionStateAPITests(TestCase):

    def test_set_resource_list(self):
        # Define an empty session
        session = SessionState([])
        # Define a resource
        old_res = Resource({'attr': 'old value'})
        # Set the resource list with the old resource
        # So here the old result is stored into a new 'R' resource
        session.set_resource_list('R', [old_res])
        # Ensure that it worked
        self.assertEqual(session._resource_map, {'R': [old_res]})
        # Define another resource
        new_res = Resource({'attr': 'new value'})
        # Now we present the second result for the same job
        session.set_resource_list('R', [new_res])
        # What should happen here is that the R resource is entirely replaced
        # by the data from the new result. The data should not be merged or
        # appended in any way.
        self.assertEqual(session._resource_map, {'R': [new_res]})

    def test_add_unit(self):
        # Define a job
        job = make_job("A")
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_unit(job)
        # The job got added to job list
        self.assertIn(job, session.job_list)
        # The job got added to job state map
        self.assertIs(session.job_state_map[job.id].job, job)
        # The job is not added to the desired job list
        self.assertNotIn(job, session.desired_job_list)
        # The job is not in the run list
        self.assertNotIn(job, session.run_list)
        # The job is not selected to run
        self.assertEqual(
            session.job_state_map[job.id].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])

    def test_add_unit_duplicate_job(self):
        # Define a job
        job = make_job("A")
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_unit(job)
        # The job got added to job list
        self.assertIn(job, session.job_list)
        # Define a perfectly identical job
        duplicate_job = make_job("A")
        self.assertEqual(job, duplicate_job)
        # Try adding it to the session
        #
        # Note that this does not raise any exceptions as the jobs are perfect
        # duplicates.
        session.add_unit(duplicate_job)
        # The new job _did not_ get added to the job list
        self.assertEqual(len(session.job_list), 1)
        self.assertIsNot(duplicate_job, session.job_list[0])

    def test_add_unit_clashing_job(self):
        # Define a job
        job = make_job("A")
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_unit(job)
        # The job got added to job list
        self.assertIn(job, session.job_list)
        # Define a different job that clashes with the initial job
        clashing_job = make_job("A", plugin='other')
        self.assertNotEqual(job, clashing_job)
        self.assertEqual(job.id, clashing_job.id)
        # Try adding it to the session
        #
        # This raises an exception
        with self.assertRaises(DependencyDuplicateError) as call:
            session.add_unit(clashing_job)
        # The exception gets job in the right order
        self.assertIs(call.exception.affected_job, job)
        self.assertIs(call.exception.affecting_job, clashing_job)
        # The new job _did not_ get added to the job list
        self.assertEqual(len(session.job_list), 1)
        self.assertIsNot(clashing_job, session.job_list[0])

    def test_add_sibling_unit(self):
        # Define a job
        job = make_job("A", summary="foo", siblings='[{"id": "B"}]')
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_unit(job)
        # Both jobs got added to job list
        self.assertEqual(len(session.job_list), 2)
        self.assertIn(job, session.job_list)
        self.assertEqual(session.job_list[1].id, 'B')
        self.assertEqual(session.job_list[1].summary, 'foo')
        sibling = session.job_list[1]
        # Both jobs got added to job state map
        self.assertIs(session.job_state_map[job.id].job, job)
        self.assertIs(session.job_state_map[sibling.id].job, sibling)
        # Both jobs are not added to the desired job list
        self.assertNotIn(job, session.desired_job_list)
        self.assertNotIn(sibling, session.desired_job_list)
        # Both jobs are not in the run list
        self.assertNotIn(job, session.run_list)
        self.assertNotIn(sibling, session.run_list)
        # Both jobs are not selected to run
        self.assertEqual(
            session.job_state_map[job.id].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])
        self.assertEqual(
            session.job_state_map[sibling.id].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])

    def test_also_after_suspend_flag(self):
        # Define a job
        job = make_job("A", summary="foo", flags='also-after-suspend')
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_unit(job)
        # Both jobs got added to job list
        self.assertEqual(len(session.job_list), 2)
        self.assertIn(job, session.job_list)
        self.assertEqual(session.job_list[1].id, 'after-suspend-A')
        self.assertEqual(session.job_list[1].summary, 'foo after suspend (S3)')
        self.assertEqual(
            session.job_list[1].depends,
            ('A com.canonical.certification::suspend/'
            'suspend_advanced_auto'))
        sibling = session.job_list[1]
        self.assertNotIn('also-after-suspend', sibling.get_flag_set())
        # Both jobs got added to job state map
        self.assertIs(session.job_state_map[job.id].job, job)
        self.assertIs(session.job_state_map[sibling.id].job, sibling)
        # Both jobs are not added to the desired job list
        self.assertNotIn(job, session.desired_job_list)
        self.assertNotIn(sibling, session.desired_job_list)
        # Both jobs are not in the run list
        self.assertNotIn(job, session.run_list)
        self.assertNotIn(sibling, session.run_list)
        # Both jobs are not selected to run
        self.assertEqual(
            session.job_state_map[job.id].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])
        self.assertEqual(
            session.job_state_map[sibling.id].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])

    def test_also_after_suspend_manual_flag(self):
        # Define a job
        job = make_job("A", summary="foo", flags='also-after-suspend-manual')
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_unit(job)
        # Both jobs got added to job list
        self.assertEqual(len(session.job_list), 2)
        self.assertIn(job, session.job_list)
        self.assertEqual(session.job_list[1].id, 'after-suspend-manual-A')
        self.assertEqual(session.job_list[1].summary, 'foo after suspend (S3)')
        self.assertEqual(
            session.job_list[1].depends,
            'A com.canonical.certification::suspend/suspend_advanced')
        sibling = session.job_list[1]
        self.assertNotIn('also-after-suspend-manual', sibling.get_flag_set())
        # Both jobs got added to job state map
        self.assertIs(session.job_state_map[job.id].job, job)
        self.assertIs(session.job_state_map[sibling.id].job, sibling)
        # Both jobs are not added to the desired job list
        self.assertNotIn(job, session.desired_job_list)
        self.assertNotIn(sibling, session.desired_job_list)
        # Both jobs are not in the run list
        self.assertNotIn(job, session.run_list)
        self.assertNotIn(sibling, session.run_list)
        # Both jobs are not selected to run
        self.assertEqual(
            session.job_state_map[job.id].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])
        self.assertEqual(
            session.job_state_map[sibling.id].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])

    def test_get_estimated_duration_auto(self):
        # Define jobs with an estimated duration
        one_second = make_job("one_second", plugin="shell",
                              command="foobar",
                              estimated_duration=1.0)
        half_second = make_job("half_second", plugin="shell",
                               command="barfoo",
                               estimated_duration=0.5)
        session = SessionState([one_second, half_second])
        session.update_desired_job_list([one_second, half_second])
        self.assertEqual(session.get_estimated_duration(), (1.5, 0.0))

    def test_get_estimated_duration_manual(self):
        two_seconds = make_job("two_seconds", plugin="manual",
                               command="farboo",
                               estimated_duration=2.0)
        shell_job = make_job("shell_job", plugin="shell",
                             command="boofar",
                             estimated_duration=0.6)
        session = SessionState([two_seconds, shell_job])
        session.update_desired_job_list([two_seconds, shell_job])
        self.assertEqual(session.get_estimated_duration(), (0.6, 32.0))

    def test_get_estimated_duration_automated_unknown(self):
        three_seconds = make_job("three_seconds", plugin="shell",
                                 command="frob",
                                 estimated_duration=3.0)
        no_estimated_duration = make_job("no_estimated_duration",
                                         plugin="shell",
                                         command="borf")
        session = SessionState([three_seconds, no_estimated_duration])
        session.update_desired_job_list([three_seconds, no_estimated_duration])
        self.assertEqual(session.get_estimated_duration(), (None, 0.0))

    def test_get_estimated_duration_manual_unknown(self):
        four_seconds = make_job("four_seconds", plugin="shell",
                                command="fibble",
                                estimated_duration=4.0)
        no_estimated_duration = make_job("no_estimated_duration",
                                         plugin="user-verify",
                                         command="bibble")
        session = SessionState([four_seconds, no_estimated_duration])
        session.update_desired_job_list([four_seconds, no_estimated_duration])
        self.assertEqual(session.get_estimated_duration(), (4.0, None))

    def test_update_mandatory_job_list_affects_run_list(self):
        A = make_job('A')
        session = SessionState([A])
        session.update_mandatory_job_list([A])
        session.update_desired_job_list([])
        self.assertEqual(session.run_list, [A])

    def test_mandatory_jobs_are_first_in_run_list(self):
        A = make_job('A')
        B = make_job('B')
        session = SessionState([A, B])
        session.update_mandatory_job_list([B])
        session.update_desired_job_list([A])
        self.assertEqual(session.run_list, [B, A])

    def test_system_information_collection_called(self):
        getter = SessionState.system_information.__get__

        self_mock = mock.MagicMock()
        self_mock._system_information = None
        with mock.patch(
            "plainbox.impl.session.state.collect_system_information"
        ) as collect_system_information_mock:
            return_value = getter(self_mock)
            self.assertEqual(
                return_value, collect_system_information_mock.return_value
            )

    def test_system_information_collection_cached(self):
        getter = SessionState.system_information.__get__
        setter = SessionState.system_information.__set__

        self_mock = mock.MagicMock()
        self_mock._system_information = None
        with mock.patch(
            "plainbox.impl.session.state.collect_system_information"
        ) as collect_system_information_mock:
            setter(self_mock, {"inxi": {}})
            self.assertFalse(collect_system_information_mock.called)

        with mock.patch(
            "plainbox.impl.session.state.collect_system_information"
        ) as collect_system_information_mock:
            return_value = getter(self_mock)
            self.assertFalse(collect_system_information_mock.called)
            self.assertEqual(return_value, {"inxi": {}})


class SessionStateTrimTests(TestCase):
    """
    Tests for SessionState.trim_job_list()
    """

    def setUp(self):
        self.job_a = make_job("a")
        self.job_b = make_job("b")
        self.origin = mock.Mock(name='origin', spec_set=Origin)
        self.session = SessionState([self.job_a, self.job_b])

    def test_trim_does_remove_jobs(self):
        """
        verify that trim_job_list() removes jobs as requested
        """
        self.session.trim_job_list(JobIdQualifier("a", self.origin))
        self.assertEqual(self.session.job_list, [self.job_b])

    def test_trim_does_remove_job_state(self):
        """
        verify that trim_job_list() removes job state for removed jobs
        """
        self.assertIn("a", self.session.job_state_map)
        self.session.trim_job_list(JobIdQualifier("a", self.origin))
        self.assertNotIn("a", self.session.job_state_map)

    def test_trim_does_remove_resources(self):
        """
        verify that trim_job_list() removes resources for removed jobs
        """
        self.session.set_resource_list("a", [Resource({'attr': 'value'})])
        self.assertIn("a", self.session.resource_map)
        self.session.trim_job_list(JobIdQualifier("a", self.origin))
        self.assertNotIn("a", self.session.resource_map)

    def test_trim_fires_on_job_removed(self):
        """
        verify that trim_job_list() fires on_job_removed() signal
        """
        signal_fired = False

        def on_job_removed(job):
            self.assertIs(job, self.job_a)
            nonlocal signal_fired
            signal_fired = True
        self.session.on_job_removed.connect(on_job_removed)
        self.session.trim_job_list(JobIdQualifier("a", self.origin))
        self.assertTrue(signal_fired)

    def test_trim_fires_on_job_state_map_changed(self):
        """
        verify that trim_job_list() fires on_job_state_map_changed() signal
        """
        signal_fired = False

        def on_job_state_map_changed():
            nonlocal signal_fired
            signal_fired = True
        self.session.on_job_state_map_changed.connect(on_job_state_map_changed)
        self.session.trim_job_list(JobIdQualifier("a", self.origin))
        self.assertTrue(signal_fired)

    def test_trim_fires_on_job_state_map_changed_only_when_needed(self):
        """
        verify that trim_job_list() does not fires on_job_state_map_changed()
        signal needlessly, when no jobs is actually being removed.
        """
        signal_fired = False

        def on_job_state_map_changed():
            nonlocal signal_fired
            signal_fired = True
        self.session.on_job_state_map_changed.connect(on_job_state_map_changed)
        self.session.trim_job_list(JobIdQualifier("x", self.origin))
        self.assertFalse(signal_fired)

    def test_trim_raises_ValueError_for_jobs_on_run_list(self):
        """
        verify that trim_job_list() raises ValueError when any of the jobs
        marked for removal is in the run_list.
        """
        self.session.update_desired_job_list([self.job_a])
        with self.assertRaises(ValueError) as boom:
            self.session.trim_job_list(JobIdQualifier("a", self.origin))
            self.assertEqual(
                str(boom.exception),
                "cannot remove jobs that are on the run list: a")


class SessionStateReactionToJobResultTests(TestCase):
    # This test checks how a simple session with a few typical job reacts to
    # job results of various kinds. It checks most of the resource presentation
    # error conditions that I could think of.

    def setUp(self):
        # All of the tests below are using one session. The session has four
        # jobs, clustered into two independent groups. Job A depends on a
        # resource provided by job R which has no dependencies at all. Job X
        # depends on job Y which in turn has no dependencies at all.
        #
        # A -(resource dependency)-> R
        #
        # X -(direct dependency) -> Y
        self.job_A = make_job("A", requires="R.attr == 'value'")
        self.job_A_expr = self.job_A.get_resource_program().expression_list[0]
        self.job_R = make_job("R", plugin="resource")
        self.job_X = make_job("X", depends='Y')
        self.job_Y = make_job("Y")
        self.job_list = [
            self.job_A, self.job_R, self.job_X, self.job_Y]
        self.session = SessionState(self.job_list)

    def job_state(self, id):
        # A helper function to avoid overly long expressions
        return self.session.job_state_map[id]

    def job_inhibitor(self, id, index):
        # Another helper that shortens deep object nesting
        return self.job_state(id).readiness_inhibitor_list[index]

    def test_assumptions(self):
        # This function checks the assumptions of SessionState initial state.
        # The job list is what we set when constructing the session.
        #
        self.assertEqual(self.session.job_list, self.job_list)
        # The run_list is still empty because the desired_job_list is equally
        # empty.
        self.assertEqual(self.session.run_list, [])
        self.assertEqual(self.session.desired_job_list, [])
        # All jobs have state objects that indicate they cannot run (because
        # they have the UNDESIRED inhibitor set for them by default).
        self.assertFalse(self.job_state('A').can_start())
        self.assertFalse(self.job_state('R').can_start())
        self.assertFalse(self.job_state('X').can_start())
        self.assertFalse(self.job_state('Y').can_start())
        self.assertEqual(self.job_inhibitor('A', 0).cause,
                         InhibitionCause.UNDESIRED)
        self.assertEqual(self.job_inhibitor('R', 0).cause,
                         InhibitionCause.UNDESIRED)
        self.assertEqual(self.job_inhibitor('X', 0).cause,
                         InhibitionCause.UNDESIRED)
        self.assertEqual(self.job_inhibitor('Y', 0).cause,
                         InhibitionCause.UNDESIRED)

    def test_desire_job_A_updates_state_map(self):
        # This function checks what happens when the job A becomes desired via
        # the update_desired_job_list() call.
        self.session.update_desired_job_list([self.job_A])
        self.assertEqual(self.session.desired_job_list, [self.job_A])
        # This should topologically sort the job list, according to the
        # relationship created by the resource requirement. This is not really
        # testing the dependency solver (it has separate tests), just that this
        # basic property is established and that the run_list properly shows
        # that R must run before A can run.
        self.assertEqual(self.session.run_list, [self.job_R, self.job_A])
        # This also recomputes job readiness state so that job R is no longer
        # undesired, has no other inhibitor and thus can start
        self.assertEqual(self.job_state('R').readiness_inhibitor_list, [])
        self.assertTrue(self.job_state('R').can_start())
        # While the A job still cannot run it now has a different inhibitor,
        # one with the PENDING_RESOURCE cause. The inhibitor also properly
        # pinpoints the related job and related expression.
        self.assertNotEqual(self.job_state('A').readiness_inhibitor_list, [])
        self.assertEqual(self.job_inhibitor('A', 0).cause,
                         InhibitionCause.PENDING_RESOURCE)
        self.assertEqual(self.job_inhibitor('A', 0).related_job, self.job_R)
        self.assertEqual(self.job_inhibitor('A', 0).related_expression,
                         self.job_A_expr)
        self.assertFalse(self.job_state('A').can_start())

    def test_resource_job_result_updates_resource_and_job_states(self):
        # This function checks what happens when a JobResult for job R (which
        # is a resource job via the resource plugin) is presented to the
        # session.
        result_R = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'io_log': [(0, 'stdout', b"attr: value\n")],
        })
        self.session.update_job_result(self.job_R, result_R)
        # The most obvious thing that can happen, is that the result is simply
        # stored in the associated job state object.
        self.assertIs(self.job_state('R').result, result_R)
        # Initially the _resource_map was empty. SessionState parses the io_log
        # of results of resource jobs and creates appropriate resource objects.
        self.assertIn("R", self.session._resource_map)
        expected = {'R': [Resource({'attr': 'value'})]}
        self.assertEqual(self.session._resource_map, expected)
        # As job results are presented to the session the readiness of other
        # jobs is changed. Since A depends on R via a resource expression and
        # the particular resource that were produced by R in this test should
        # allow the expression to match the readiness inhibitor from A should
        # have been removed. Since this test does not use
        # update_desired_job_list() a will still have the UNDESIRED inhibitor
        # but it will no longer have the PENDING_RESOURCE inhibitor,
        self.assertEqual(self.job_inhibitor('A', 0).cause,
                         InhibitionCause.UNDESIRED)
        # Now if we put A on the desired list this should clear the UNDESIRED
        # inhibitor and make A runnable.
        self.session.update_desired_job_list([self.job_A])
        self.assertTrue(self.job_state('A').can_start())

    def test_normal_job_result_updates(self):
        # This function checks what happens when a JobResult for job A is
        # presented to the session. Set the outcome to a "different" value as
        # the initial job result was pretty much identical and the comparison
        # below would fail to work as the update would have been silently
        # ignored.
        result_A = MemoryJobResult({'outcome': 'different'})
        self.session.update_job_result(self.job_A, result_A)
        # As before the result should be stored as-is
        self.assertIs(self.job_state('A').result, result_A)
        # Unlike before _resource_map should be left unchanged
        self.assertEqual(self.session._resource_map, {})
        # One interesting observation is that readiness inhibitors are entirely
        # unaffected by existing test results beyond dependency and resource
        # relationships. While a result for job A was presented, job A is still
        # inhibited by the UNDESIRED inhibitor.
        self.assertEqual(self.job_inhibitor('A', 0).cause,
                         InhibitionCause.UNDESIRED)

    @mock.patch('plainbox.impl.ctrl.logger')
    def test_resource_job_with_broken_output(self, mock_logger):
        # This function checks how SessionState parses partially broken
        # resource jobs.  A JobResult with broken output is constructed below.
        # The output will describe one proper record, one broken record and
        # another proper record in that order.
        result_R = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'io_log': [
                (0, 'stdout', b"attr: value-1\n"),
                (1, 'stdout', b"\n"),
                (1, 'stdout', b"I-sound-like-a-broken-record\n"),
                (1, 'stdout', b"\n"),
                (1, 'stdout', b"attr: value-2\n")
            ],
        })
        # Since we cannot control the output of scripts and people indeed make
        # mistakes a warning is issued but no exception is raised to the
        # caller.
        self.session.update_job_result(self.job_R, result_R)
        # The observation here is that the parser is not handling the exception
        # in away which would allow for recovery. Out of all the output only
        # the first record is created and stored properly. The third, proper
        # record is entirely ignored.
        expected = {'R': [Resource({'attr': 'value-1'})]}
        self.assertEqual(self.session._resource_map, expected)

        # Make sure the right warning was logged
        mock_logger.warning.assert_called_once_with(
            "local script %s returned invalid RFC822 data: %s",
            self.job_R.id, RFC822SyntaxError(None, 3,
                "Unexpected non-empty line: "
                "'I-sound-like-a-broken-record\\n'"))

    def test_desire_job_X_updates_state_map(self):
        # This function checks what happens when the job X becomes desired via
        # the update_desired_job_list() call.
        self.session.update_desired_job_list([self.job_X])
        self.assertEqual(self.session.desired_job_list, [self.job_X])
        # As in the similar A - R test function above this topologically sorts
        # all affected jobs. Here X depends on Y so Y should be before X on the
        # run list.
        self.assertEqual(self.session.run_list, [self.job_Y, self.job_X])
        # As in the A - R test above this also recomputes the job readiness
        # state. Job Y is now runnable but job X has a PENDING_DEP inhibitor.
        self.assertEqual(self.job_state('Y').readiness_inhibitor_list, [])
        # While the A job still cannot run it now has a different inhibitor,
        # one with the PENDING_RESOURCE cause. The inhibitor also properly
        # pinpoints the related job and related expression.
        self.assertNotEqual(self.job_state('X').readiness_inhibitor_list, [])
        self.assertEqual(self.job_inhibitor('X', 0).cause,
                         InhibitionCause.PENDING_DEP)
        self.assertEqual(self.job_inhibitor('X', 0).related_job, self.job_Y)
        self.assertFalse(self.job_state('X').can_start())

    def test_desired_job_X_cannot_run_with_failed_job_Y(self):
        # This function checks how SessionState reacts when the desired job X
        # readiness state changes when presented with a failed result to job Y
        self.session.update_desired_job_list([self.job_X])
        # When X is desired, as above, it should be inhibited with PENDING_DEP
        # on Y
        self.assertNotEqual(self.job_state('X').readiness_inhibitor_list, [])
        self.assertEqual(self.job_inhibitor('X', 0).cause,
                         InhibitionCause.PENDING_DEP)
        self.assertEqual(self.job_inhibitor('X', 0).related_job, self.job_Y)
        self.assertFalse(self.job_state('X').can_start())
        # When a failed Y result is presented X should switch to FAILED_DEP
        result_Y = MemoryJobResult({'outcome': IJobResult.OUTCOME_FAIL})
        self.session.update_job_result(self.job_Y, result_Y)
        # Now job X should have a FAILED_DEP inhibitor instead of the
        # PENDING_DEP it had before. Everything else should stay as-is.
        self.assertNotEqual(self.job_state('X').readiness_inhibitor_list, [])
        self.assertEqual(self.job_inhibitor('X', 0).cause,
                         InhibitionCause.FAILED_DEP)
        self.assertEqual(self.job_inhibitor('X', 0).related_job, self.job_Y)
        self.assertFalse(self.job_state('X').can_start())

    def test_desired_job_X_can_run_with_passing_job_Y(self):
        # A variant of the test case above, simply Y passes this time, making X
        # runnable
        self.session.update_desired_job_list([self.job_X])
        result_Y = MemoryJobResult({'outcome': IJobResult.OUTCOME_PASS})
        self.session.update_job_result(self.job_Y, result_Y)
        # Now X is runnable
        self.assertEqual(self.job_state('X').readiness_inhibitor_list, [])
        self.assertTrue(self.job_state('X').can_start())

    def test_desired_job_X_cannot_run_with_no_resource_R(self):
        # A variant of the two test cases above, using A-R jobs
        self.session.update_desired_job_list([self.job_A])
        result_R = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'io_log': [(0, 'stdout', b'attr: wrong value\n')],
        })
        self.session.update_job_result(self.job_R, result_R)
        # Now A is inhibited by FAILED_RESOURCE
        self.assertNotEqual(self.job_state('A').readiness_inhibitor_list, [])
        self.assertEqual(self.job_inhibitor('A', 0).cause,
                         InhibitionCause.FAILED_RESOURCE)
        self.assertEqual(self.job_inhibitor('A', 0).related_job, self.job_R)
        self.assertEqual(self.job_inhibitor('A', 0).related_expression,
                         self.job_A_expr)
        self.assertFalse(self.job_state('A').can_start())

    def test_resource_job_result_overwrites_old_resources(self):
        # This function checks what happens when a JobResult for job R is
        # presented to a session that has some resources from that job already.
        result_R_old = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'io_log': [(0, 'stdout', b"attr: old value\n")]
        })
        self.session.update_job_result(self.job_R, result_R_old)
        # So here the old result is stored into a new 'R' resource
        expected_before = {'R': [Resource({'attr': 'old value'})]}
        self.assertEqual(self.session._resource_map, expected_before)
        # Now we present the second result for the same job
        result_R_new = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'io_log': [(0, 'stdout', b"attr: new value\n")]
        })
        self.session.update_job_result(self.job_R, result_R_new)
        # What should happen here is that the R resource is entirely replaced
        # by the data from the new result. The data should not be merged or
        # appended in any way.
        expected_after = {'R': [Resource({'attr': 'new value'})]}
        self.assertEqual(self.session._resource_map, expected_after)

    def test_get_outcome_stats(self):
        result_A = MemoryJobResult({'outcome': IJobResult.OUTCOME_PASS})
        result_R = MemoryJobResult({'outcome': IJobResult.OUTCOME_FAIL})
        result_Y = MemoryJobResult({'outcome': IJobResult.OUTCOME_FAIL})
        self.session.update_job_result(self.job_A, result_A)
        self.session.update_job_result(self.job_R, result_R)
        self.session.update_job_result(self.job_Y, result_Y)
        self.assertEqual(self.session.get_outcome_stats(),
                         {IJobResult.OUTCOME_PASS: 1,
                          IJobResult.OUTCOME_FAIL: 2})

    def test_get_certification_status_map(self):
        result_A = MemoryJobResult({'outcome': IJobResult.OUTCOME_PASS})
        self.session.update_job_result(self.job_A, result_A)
        self.session.job_state_map[
            self.job_A.id].effective_certification_status = 'foo'
        self.assertEqual(self.session.get_certification_status_map(), {})
        self.assertEqual(self.session.get_certification_status_map(
            outcome_filter=(IJobResult.OUTCOME_PASS,),
            certification_status_filter=('foo',)),
            {self.job_A.id: self.session.job_state_map[self.job_A.id]})
        result_Y = MemoryJobResult({'outcome': IJobResult.OUTCOME_FAIL})
        self.session.job_state_map[
            self.job_Y.id].effective_certification_status = 'bar'
        self.assertEqual(self.session.get_certification_status_map(), {})
        self.assertEqual(self.session.get_certification_status_map(
            outcome_filter=(IJobResult.OUTCOME_PASS, IJobResult.OUTCOME_FAIL),
            certification_status_filter=('foo', 'bar')),
            {self.job_A.id: self.session.job_state_map[self.job_A.id]})
        self.session.update_job_result(self.job_Y, result_Y)
        self.assertEqual(self.session.get_certification_status_map(
            outcome_filter=(IJobResult.OUTCOME_PASS, IJobResult.OUTCOME_FAIL),
            certification_status_filter=('foo', 'bar')),
            {self.job_A.id: self.session.job_state_map[self.job_A.id],
             self.job_Y.id: self.session.job_state_map[self.job_Y.id]})


class SessionMetadataTests(TestCase):

    def test_smoke(self):
        metadata = SessionMetaData()
        self.assertEqual(metadata.title, None)
        self.assertEqual(metadata.flags, set())
        self.assertEqual(metadata.running_job_name, None)

    def test_initializer(self):
        metadata = SessionMetaData(
            title="title", flags=['f1', 'f2'], running_job_name='id')
        self.assertEqual(metadata.title, "title")
        self.assertEqual(metadata.flags, set(["f1", "f2"]))
        self.assertEqual(metadata.running_job_name, "id")

    def test_accessors(self):
        metadata = SessionMetaData()
        metadata.title = "title"
        self.assertEqual(metadata.title, "title")
        metadata.flags = set(["f1", "f2"])
        self.assertEqual(metadata.flags, set(["f1", "f2"]))
        metadata.running_job_name = "id"
        self.assertEqual(metadata.running_job_name, "id")

    def test_app_blob_default_value(self):
        metadata = SessionMetaData()
        self.assertIs(metadata.app_blob, b'')

    def test_app_blob_assignment(self):
        metadata = SessionMetaData()
        metadata.app_blob = b'blob'
        self.assertEqual(metadata.app_blob, b'blob')
        metadata.app_blob = None
        self.assertEqual(metadata.app_blob, None)

    def test_app_blob_kwarg_to_init(self):
        metadata = SessionMetaData(app_blob=b'blob')
        self.assertEqual(metadata.app_blob, b'blob')

    def test_app_id_default_value(self):
        metadata = SessionMetaData()
        self.assertIs(metadata.app_id, None)

    def test_app_id_assignment(self):
        metadata = SessionMetaData()
        metadata.app_id = 'com.canonical.certification.plainbox'
        self.assertEqual(
            metadata.app_id, 'com.canonical.certification.plainbox')
        metadata.app_id = None
        self.assertEqual(metadata.app_id, None)

    def test_app_id_kwarg_to_init(self):
        metadata = SessionMetaData(
            app_id='com.canonical.certification.plainbox')
        self.assertEqual(
            metadata.app_id, 'com.canonical.certification.plainbox')


class SessionDeviceContextTests(SignalTestCase):

    def setUp(self):
        self.ctx = SessionDeviceContext()
        self.provider = mock.Mock(name='provider', spec_set=Provider1)
        self.unit = mock.Mock(name='unit', spec_set=UnitWithId)
        self.unit.provider = self.provider
        self.provider.unit_list = [self.unit]
        self.provider.problem_list = []
        self.job = mock.Mock(name='job', spec_set=JobDefinition, siblings=None)
        self.job.get_flag_set = mock.Mock(return_value=())
        self.job.Meta.name = 'job'

    def test_smoke(self):
        """
        Ensure that you can create a session device context and that
        default values are what we expect
        """
        self.assertIsNone(self.ctx.device)
        self.assertIsInstance(self.ctx.state, SessionState)
        self.assertEqual(self.ctx.provider_list, [])
        self.assertEqual(self.ctx.unit_list, [])

    def test_add_provider(self):
        """
        Ensure that adding a provider works
        """
        self.ctx.add_provider(self.provider)
        self.assertIn(self.provider, self.ctx.provider_list)

    def test_add_provider_twice(self):
        """
        Ensure that you cannot add a provider twice
        """
        self.ctx.add_provider(self.provider)
        with self.assertRaises(ValueError):
            self.ctx.add_provider(self.provider)

    def test_add_provider__adds_units(self):
        """
        Ensure that adding a provider adds the unit it knows about
        """
        self.ctx.add_provider(self.provider)
        self.assertIn(self.unit, self.ctx.unit_list)

    def test_add_unit(self):
        """
        Ensure that adding an unit works
        """
        self.ctx.add_unit(self.unit)
        self.assertIn(self.unit, self.ctx.unit_list)
        self.assertIn(self.unit, self.ctx.state.unit_list)

    def test_add_unit__job_unit(self):
        """
        Ensure that adding a job unit works
        """
        self.ctx.add_unit(self.job)
        self.assertIn(self.job, self.ctx.unit_list)
        self.assertIn(self.job, self.ctx.state.unit_list)
        self.assertIn(self.job, self.ctx.state.job_list)

    def test_add_unit_twice(self):
        """
        Ensure that you cannot add an unit twice
        """
        self.ctx.add_unit(self.unit)
        with self.assertRaises(ValueError):
            self.ctx.add_unit(self.unit)

    def test_remove_unit(self):
        """
        Ensure that removing an unit works
        """
        self.ctx.add_unit(self.unit)
        self.ctx.remove_unit(self.unit)
        self.assertNotIn(self.unit, self.ctx.unit_list)
        self.assertNotIn(self.unit, self.ctx.state.unit_list)

    def test_remove_unit__missing(self):
        """
        Ensure that you cannot remove an unit that is not added first
        """
        with self.assertRaises(ValueError):
            self.ctx.remove_unit(self.unit)

    def test_remove_job_unit(self):
        """
        Ensure that removing a job unit works
        """
        self.ctx.add_unit(self.job)
        self.ctx.remove_unit(self.job)
        self.assertNotIn(self.job, self.ctx.unit_list)
        self.assertNotIn(self.job, self.ctx.state.unit_list)
        self.assertNotIn(self.job, self.ctx.state.job_list)
        self.assertNotIn(self.job.id, self.ctx.state.job_state_map)
        self.assertNotIn(self.job.id, self.ctx.state.resource_map)

    def test_on_unit_added__via_ctx(self):
        """
        Ensure that adding units produces same/correct signals
        regardless of how that unit is added. This test checks the scenario
        that happens when the context is used directly
        """
        self.watchSignal(self.ctx.on_unit_added)
        self.watchSignal(self.ctx.state.on_unit_added)
        self.watchSignal(self.ctx.state.on_job_added)
        self.ctx.add_unit(self.unit)
        sig1 = self.assertSignalFired(self.ctx.on_unit_added, self.unit)
        sig2 = self.assertSignalFired(self.ctx.state.on_unit_added, self.unit)
        self.assertSignalOrdering(sig1, sig2)
        self.assertSignalNotFired(self.ctx.state.on_job_added, self.unit)

    def test_on_unit_added__via_state(self):
        """
        Ensure that adding units produces same/correct signals
        regardless of how that unit is added. This test checks the scenario
        that happens when the session state is used.
        """
        self.watchSignal(self.ctx.on_unit_added)
        self.watchSignal(self.ctx.state.on_unit_added)
        self.watchSignal(self.ctx.state.on_job_added)
        self.ctx.state.add_unit(self.unit)
        sig1 = self.assertSignalFired(self.ctx.on_unit_added, self.unit)
        sig2 = self.assertSignalFired(self.ctx.state.on_unit_added, self.unit)
        self.assertSignalOrdering(sig1, sig2)
        self.assertSignalNotFired(self.ctx.state.on_job_added, self.unit)

    def test_on_job_added__via_ctx(self):
        """
        Ensure that adding job units produces same/correct signals
        regardless of how that job is added. This test checks the scenario
        that happens when the context is used directly
        """
        self.watchSignal(self.ctx.on_unit_added)
        self.watchSignal(self.ctx.state.on_unit_added)
        self.watchSignal(self.ctx.state.on_job_added)
        self.ctx.add_unit(self.job)
        sig1 = self.assertSignalFired(self.ctx.on_unit_added, self.job)
        sig2 = self.assertSignalFired(self.ctx.state.on_unit_added, self.job)
        sig3 = self.assertSignalFired(self.ctx.state.on_job_added, self.job)
        self.assertSignalOrdering(sig1, sig2, sig3)

    def test_on_job_added__via_state(self):
        """
        Ensure that adding job units produces same/correct signals
        regardless of how that job is added. This test checks the scenario
        that happens when the session state is used.
        """
        self.watchSignal(self.ctx.on_unit_added)
        self.watchSignal(self.ctx.state.on_unit_added)
        self.watchSignal(self.ctx.state.on_job_added)
        self.ctx.state.add_unit(self.job)
        sig1 = self.assertSignalFired(self.ctx.on_unit_added, self.job)
        sig2 = self.assertSignalFired(self.ctx.state.on_unit_added, self.job)
        sig3 = self.assertSignalFired(self.ctx.state.on_job_added, self.job)
        self.assertSignalOrdering(sig1, sig2, sig3)

    def test_on_unit_removed__via_ctx(self):
        """
        Ensure that removing units produces same/correct signals
        regardless of how that unit is removed. This test checks the scenario
        that happens when the context is used directly
        """
        self.ctx.add_unit(self.unit)
        self.watchSignal(self.ctx.on_unit_removed)
        self.watchSignal(self.ctx.state.on_unit_removed)
        self.watchSignal(self.ctx.state.on_job_removed)
        self.ctx.remove_unit(self.unit)
        sig1 = self.assertSignalFired(self.ctx.on_unit_removed, self.unit)
        sig2 = self.assertSignalFired(
            self.ctx.state.on_unit_removed, self.unit)
        self.assertSignalOrdering(sig1, sig2)
        self.assertSignalNotFired(self.ctx.state.on_job_removed, self.unit)

    def test_on_unit_removed__via_state(self):
        """
        Ensure that removing units produces same/correct signals
        regardless of how that unit is removed. This test checks the scenario
        that happens when the session state is used.
        """
        self.ctx.add_unit(self.unit)
        self.watchSignal(self.ctx.on_unit_removed)
        self.watchSignal(self.ctx.state.on_unit_removed)
        self.watchSignal(self.ctx.state.on_job_removed)
        self.ctx.state.remove_unit(self.unit)
        sig1 = self.assertSignalFired(self.ctx.on_unit_removed, self.unit)
        sig2 = self.assertSignalFired(
            self.ctx.state.on_unit_removed, self.unit)
        self.assertSignalOrdering(sig1, sig2)
        self.assertSignalNotFired(self.ctx.state.on_job_removed, self.unit)

    def test_on_job_removed__via_ctx(self):
        """
        Ensure that removing job units produces same/correct signals
        regardless of how that job is removed. This test checks the scenario
        that happens when the context is used directly
        """
        self.ctx.add_unit(self.job)
        self.watchSignal(self.ctx.on_unit_removed)
        self.watchSignal(self.ctx.state.on_unit_removed)
        self.watchSignal(self.ctx.state.on_job_removed)
        self.ctx.remove_unit(self.job)
        sig1 = self.assertSignalFired(self.ctx.on_unit_removed, self.job)
        sig2 = self.assertSignalFired(self.ctx.state.on_unit_removed, self.job)
        sig3 = self.assertSignalFired(self.ctx.state.on_job_removed, self.job)
        self.assertSignalOrdering(sig1, sig2, sig3)

    def test_on_job_removed__via_state(self):
        """
        Ensure that removing job units produces same/correct signals
        regardless of how that job is removed. This test checks the scenario
        that happens when the session state is used.
        """
        self.ctx.add_unit(self.job)
        self.watchSignal(self.ctx.on_unit_removed)
        self.watchSignal(self.ctx.state.on_unit_removed)
        self.watchSignal(self.ctx.state.on_job_removed)
        self.ctx.state.remove_unit(self.job)
        sig1 = self.assertSignalFired(self.ctx.on_unit_removed, self.job)
        sig2 = self.assertSignalFired(self.ctx.state.on_unit_removed, self.job)
        sig3 = self.assertSignalFired(self.ctx.state.on_job_removed, self.job)
        self.assertSignalOrdering(sig1, sig2, sig3)
