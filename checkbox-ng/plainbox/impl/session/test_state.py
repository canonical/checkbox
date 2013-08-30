# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
plainbox.impl.test_session
==========================

Test definitions for plainbox.impl.session module
"""

from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.depmgr import DependencyMissingError
from plainbox.impl.resource import Resource
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session import JobReadinessInhibitor
from plainbox.impl.session import SessionState
from plainbox.impl.session import UndesiredJobReadinessInhibitor
from plainbox.impl.session.state import SessionMetaData
from plainbox.impl.testing_utils import make_job


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


class RegressionTests(TestCase):
    # Tests for bugfixes

    def test_crash_in_update_desired_job_list(self):
        # This checks if a DependencyError can cause crash
        # update_desired_job_list() with a ValueError, in certain conditions.
        A = make_job('A', depends='X')
        L = make_job('L', plugin='local')
        session = SessionState([A, L])
        problems = session.update_desired_job_list([A, L])
        # We should get exactly one DependencyMissingError related to job A and
        # the undefined job X (that is presumably defined by the local job L)
        self.assertEqual(len(problems), 1)
        self.assertIsInstance(problems[0], DependencyMissingError)
        self.assertIs(problems[0].affected_job, A)

    def test_init_with_identical_jobs(self):
        A = make_job("A")
        second_A = make_job("A")
        third_A = make_job("A")
        # Identical jobs are folded for backwards compatibility with some local
        # jobs that re-added existing jobs
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

    def test_add_job(self):
        # Define a job
        job = make_job("A")
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_job(job)
        # The job got added to job list
        self.assertIn(job, session.job_list)
        # The job got added to job state map
        self.assertIs(session.job_state_map[job.name].job, job)
        # The job is not added to the desired job list
        self.assertNotIn(job, session.desired_job_list)
        # The job is not in the run list
        self.assertNotIn(job, session.run_list)
        # The job is not selected to run
        self.assertEqual(
            session.job_state_map[job.name].readiness_inhibitor_list,
            [UndesiredJobReadinessInhibitor])

    def test_add_job_duplicate_job(self):
        # Define a job
        job = make_job("A")
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_job(job)
        # The job got added to job list
        self.assertIn(job, session.job_list)
        # Define a perfectly identical job
        duplicate_job = make_job("A")
        self.assertEqual(job, duplicate_job)
        # Try adding it to the session
        #
        # Note that this does not raise any exceptions as the jobs are perfect
        # duplicates.
        session.add_job(duplicate_job)
        # The new job _did not_ get added to the job list
        self.assertEqual(len(session.job_list), 1)
        self.assertIsNot(duplicate_job, session.job_list[0])

    def test_add_job_clashing_job(self):
        # Define a job
        job = make_job("A")
        # Define an empty session
        session = SessionState([])
        # Add the job to the session
        session.add_job(job)
        # The job got added to job list
        self.assertIn(job, session.job_list)
        # Define a different job that clashes with the initial job
        clashing_job = make_job("A", plugin='other')
        self.assertNotEqual(job, clashing_job)
        self.assertEqual(job.name, clashing_job.name)
        # Try adding it to the session
        #
        # This raises an exception
        with self.assertRaises(DependencyDuplicateError) as call:
            session.add_job(clashing_job)
        # The exception gets job in the right order
        self.assertIs(call.exception.affected_job, job)
        self.assertIs(call.exception.affecting_job, clashing_job)
        # The new job _did not_ get added to the job list
        self.assertEqual(len(session.job_list), 1)
        self.assertIsNot(clashing_job, session.job_list[0])

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


class SessionStateSpecialTests(TestCase):

    # NOTE: those tests are essential. They allow testing the behavior of
    # complex stuff like resource jobs and local jobs in total isolation from
    # the actual job runner with relative simplicity.
    #
    # There are many scenarios that need to be tested that I can think of right
    # now. All the failure conditions are interesting as they are less likely
    # to occur during typical correct operation. A few of those from the top of
    # my head:
    #
    # *) resource job output altering the resource map
    # *) resource changes altering the readiness state of jobs
    # *) test results being remembered (those should be renamed to job results)
    # *) local job output altering job list
    # *) attachment job output altering yet unimplemented attachment store
    #
    # Local jobs are of super consideration as they can trigger various
    # interesting error conditions (all of which are reported by the dependency
    # solver as DependencyError objects. One interesting aspect of job
    # generation is how an error that resulted by adding a job is resolved. Are
    # we removing the newly-added job or some other job that was affected by
    # the introduction of a new job? How are we handling duplicates? In all
    # such cases it is important to properly track job origin to provide
    # informative and correct error messages both at the UI level (hopefully
    # our data won't cause such errors on a daily basis) but more importantly
    # at the developer-console level where developers are actively spending
    # most of their time adding (changing) jobs in an ever-growing pile that
    # they don't necessarily fully know, comprehend or remember.

    def test_resource_job_affects_resources(self):
        pass


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
        self.job_L = make_job("L", plugin="local")
        self.job_list = [
            self.job_A, self.job_R, self.job_X, self.job_Y, self.job_L]
        self.session = SessionState(self.job_list)

    def job_state(self, name):
        # A helper function to avoid overly long expressions
        return self.session.job_state_map[name]

    def job_inhibitor(self, name, index):
        # Another helper that shortens deep object nesting
        return self.job_state(name).readiness_inhibitor_list[index]

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
                         JobReadinessInhibitor.UNDESIRED)
        self.assertEqual(self.job_inhibitor('R', 0).cause,
                         JobReadinessInhibitor.UNDESIRED)
        self.assertEqual(self.job_inhibitor('X', 0).cause,
                         JobReadinessInhibitor.UNDESIRED)
        self.assertEqual(self.job_inhibitor('Y', 0).cause,
                         JobReadinessInhibitor.UNDESIRED)

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
                         JobReadinessInhibitor.PENDING_RESOURCE)
        self.assertEqual(self.job_inhibitor('A', 0).related_job, self.job_R)
        self.assertEqual(self.job_inhibitor('A', 0).related_expression,
                         self.job_A_expr)
        self.assertFalse(self.job_state('A').can_start())

    def test_resource_job_result_updates_resource_and_job_states(self):
        # This function checks what happens when a JobResult for job R (which
        # is a resource job via the resource plugin) is presented to the
        # session.
        result_R = MemoryJobResult({
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
                         JobReadinessInhibitor.UNDESIRED)
        # Now if we put A on the desired list this should clear the UNDESIRED
        # inhibitor and make A runnable.
        self.session.update_desired_job_list([self.job_A])
        self.assertTrue(self.job_state('A').can_start())

    def test_normal_job_result_updates(self):
        # This function checks what happens when a JobResult for job A is
        # presented to the session.
        result_A = MemoryJobResult({})
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
                         JobReadinessInhibitor.UNDESIRED)

    def test_resource_job_with_broken_output(self):
        # This function checks how SessionState parses partially broken
        # resource jobs.  A JobResult with broken output is constructed below.
        # The output will describe one proper record, one broken record and
        # another proper record in that order.
        result_R = MemoryJobResult({
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
                         JobReadinessInhibitor.PENDING_DEP)
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
                         JobReadinessInhibitor.PENDING_DEP)
        self.assertEqual(self.job_inhibitor('X', 0).related_job, self.job_Y)
        self.assertFalse(self.job_state('X').can_start())
        # When a failed Y result is presented X should switch to FAILED_DEP
        result_Y = MemoryJobResult({'outcome': IJobResult.OUTCOME_FAIL})
        self.session.update_job_result(self.job_Y, result_Y)
        # Now job X should have a FAILED_DEP inhibitor instead of the
        # PENDING_DEP it had before. Everything else should stay as-is.
        self.assertNotEqual(self.job_state('X').readiness_inhibitor_list, [])
        self.assertEqual(self.job_inhibitor('X', 0).cause,
                         JobReadinessInhibitor.FAILED_DEP)
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
            'io_log': [(0, 'stdout', b'attr: wrong value\n')],
        })
        self.session.update_job_result(self.job_R, result_R)
        # Now A is inhibited by FAILED_RESOURCE
        self.assertNotEqual(self.job_state('A').readiness_inhibitor_list, [])
        self.assertEqual(self.job_inhibitor('A', 0).cause,
                         JobReadinessInhibitor.FAILED_RESOURCE)
        self.assertEqual(self.job_inhibitor('A', 0).related_job, self.job_R)
        self.assertEqual(self.job_inhibitor('A', 0).related_expression,
                         self.job_A_expr)
        self.assertFalse(self.job_state('A').can_start())

    def test_resource_job_result_overwrites_old_resources(self):
        # This function checks what happens when a JobResult for job R is
        # presented to a session that has some resources from that job already.
        result_R_old = MemoryJobResult({
            'io_log': [(0, 'stdout', b"attr: old value\n")]
        })
        self.session.update_job_result(self.job_R, result_R_old)
        # So here the old result is stored into a new 'R' resource
        expected_before = {'R': [Resource({'attr': 'old value'})]}
        self.assertEqual(self.session._resource_map, expected_before)
        # Now we present the second result for the same job
        result_R_new = MemoryJobResult({
            'io_log': [(0, 'stdout', b"attr: new value\n")]
        })
        self.session.update_job_result(self.job_R, result_R_new)
        # What should happen here is that the R resource is entirely replaced
        # by the data from the new result. The data should not be merged or
        # appended in any way.
        expected_after = {'R': [Resource({'attr': 'new value'})]}
        self.assertEqual(self.session._resource_map, expected_after)

    def test_local_job_creates_jobs(self):
        # Create a result for the local job L
        result_L = MemoryJobResult({
            'io_log': [
                (0, 'stdout', b'name: foo\n'),
                (1, 'stdout', b'plugin: manual\n'),
            ],
        })
        # Show this result to the session
        self.session.update_job_result(self.job_L, result_L)
        # A job should be generated
        self.assertTrue("foo" in self.session.job_state_map)
        job_foo = self.session.job_state_map['foo'].job
        self.assertTrue(job_foo.name, "foo")
        self.assertTrue(job_foo.plugin, "manual")
        # It should be linked to the job L via the via attribute
        self.assertTrue(job_foo.via, self.job_L.get_checksum())


class SessionMetadataTests(TestCase):

    def test_smoke(self):
        metadata = SessionMetaData()
        self.assertEqual(metadata.title, None)
        self.assertEqual(metadata.flags, set())
        self.assertEqual(metadata.running_job_name, None)

    def test_initializer(self):
        metadata = SessionMetaData(
            title="title", flags=['f1', 'f2'], running_job_name='name')
        self.assertEqual(metadata.title, "title")
        self.assertEqual(metadata.flags, set(["f1", "f2"]))
        self.assertEqual(metadata.running_job_name, "name")

    def test_accessors(self):
        metadata = SessionMetaData()
        metadata.title = "title"
        self.assertEqual(metadata.title, "title")
        metadata.flags = set(["f1", "f2"])
        self.assertEqual(metadata.flags, set(["f1", "f2"]))
        metadata.running_job_name = "name"
        self.assertEqual(metadata.running_job_name, "name")

    def test_as_json(self):
        metadata = SessionMetaData()
        metadata.title = "title"
        metadata.flags = set(["f1", "f2"])
        metadata.running_job_name = "name"
        self.assertEqual(metadata.as_json(), {
            "title": "title",
            "flags": ["f1", "f2"],
            "running_job_name": "name"
        })
