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
plainbox.impl.test_session
==========================

Test definitions for plainbox.impl.session module
"""

import json
import os
import tempfile
import shutil

from tempfile import TemporaryDirectory
from unittest import TestCase

from plainbox.impl.depmgr import DependencyMissingError
from plainbox.impl.resource import Resource
from plainbox.impl.result import JobResult
from plainbox.impl.session import JobReadinessInhibitor
from plainbox.impl.session import JobState
from plainbox.impl.session import SessionState
from plainbox.impl.session import SessionStateEncoder
from plainbox.impl.session import UndesiredJobReadinessInhibitor
from plainbox.impl.testing_utils import make_io_log, make_job, make_job_result


class JobReadinessInhibitorTests(TestCase):

    def test_bad_initialization(self):
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.UNDESIRED - 1)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.FAILED_RESOURCE + 1)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.PENDING_DEP)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.FAILED_DEP)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.PENDING_RESOURCE)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.FAILED_RESOURCE)
        job = make_job("A")
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.PENDING_RESOURCE, job)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          JobReadinessInhibitor.FAILED_RESOURCE, job)

    def test_unknown(self):
        obj = JobReadinessInhibitor(JobReadinessInhibitor.UNDESIRED)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:UNDESIRED"
                " related_job:None"
                " related_expression:None>"))
        self.assertEqual(str(obj), "undesired")

    def test_pending_dep(self):
        job = make_job("A")
        obj = JobReadinessInhibitor(
            JobReadinessInhibitor.PENDING_DEP, related_job=job)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:PENDING_DEP"
                " related_job:<JobDefinition name:'A' plugin:'dummy'>"
                " related_expression:None>"))
        self.assertEqual(str(obj), "required dependency 'A' did not run yet")

    def test_failed_dep(self):
        job = make_job("A")
        obj = JobReadinessInhibitor(
            JobReadinessInhibitor.FAILED_DEP, related_job=job)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:FAILED_DEP"
                " related_job:<JobDefinition name:'A' plugin:'dummy'>"
                " related_expression:None>"))
        self.assertEqual(str(obj), "required dependency 'A' has failed")

    def test_pending_resource(self):
        job = make_job("A", requires="resource.attr == 'value'")
        expr = job.get_resource_program().expression_list[0]
        obj = JobReadinessInhibitor(
            JobReadinessInhibitor.PENDING_RESOURCE, related_job=job,
            related_expression=expr)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:PENDING_RESOURCE"
                " related_job:<JobDefinition name:'A' plugin:'dummy'>"
                " related_expression:"
                "<ResourceExpression text:\"resource.attr == 'value'\">>"))
        self.assertEqual(
            str(obj), (
                "resource expression \"resource.attr == 'value'\" could not be"
                " evaluated because the resource it depends on did not run"
                " yet"))

    def test_failed_resource(self):
        job = make_job("A", requires="resource.attr == 'value'")
        expr = job.get_resource_program().expression_list[0]
        obj = JobReadinessInhibitor(
            JobReadinessInhibitor.FAILED_RESOURCE, related_job=job,
            related_expression=expr)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:FAILED_RESOURCE"
                " related_job:<JobDefinition name:'A' plugin:'dummy'>"
                " related_expression:"
                "<ResourceExpression text:\"resource.attr == 'value'\">>"))
        self.assertEqual(
            str(obj), (
                "resource expression \"resource.attr == 'value'\""
                " evaluates to false"))

    def test_unknown_global(self):
        self.assertEqual(UndesiredJobReadinessInhibitor.cause,
                         JobReadinessInhibitor.UNDESIRED)


class JobStateTests(TestCase):

    def setUp(self):
        self.job = make_job("A")
        self.job_state = JobState(self.job)

    def test_smoke(self):
        self.assertIsNotNone(self.job_state.result)
        self.assertIs(self.job_state.result.job, self.job)
        self.assertIs(self.job_state.result.outcome, JobResult.OUTCOME_NONE)
        self.assertEqual(self.job_state.readiness_inhibitor_list, [
            UndesiredJobReadinessInhibitor])

    def test_getting_job(self):
        self.assertIs(self.job_state.job, self.job)

    def test_setting_job_is_not_allowed(self):
        with self.assertRaises(AttributeError):
            self.job_state.job = None

    def test_setting_result(self):
        result = make_job_result(self.job)
        self.job_state.result = result
        self.assertIs(self.job_state.result, result)

    def test_setting_readiness_inhibitor_list(self):
        inhibitor = JobReadinessInhibitor(JobReadinessInhibitor.UNDESIRED)
        self.job_state.readiness_inhibitor_list = [inhibitor]
        self.assertEqual(self.job_state.readiness_inhibitor_list, [inhibitor])

    def test_can_start(self):
        self.job_state.readiness_inhibitor_list = []
        self.assertTrue(self.job_state.can_start())
        self.job_state.readiness_inhibitor_list = [
            UndesiredJobReadinessInhibitor]
        self.assertFalse(self.job_state.can_start())

    def test_readiness_description(self):
        self.job_state.readiness_inhibitor_list = []
        self.assertEqual(self.job_state.get_readiness_description(),
                         "job can be started")
        self.job_state.readiness_inhibitor_list = [
            UndesiredJobReadinessInhibitor]
        self.assertTrue(
            self.job_state.get_readiness_description().startswith(
                "job cannot be started: "))

    def test_encode_resource_job(self):
        self.job_R = make_job("R", plugin="resource")
        result_R = JobResult({
            'job': self.job_R,
            'outcome': JobResult.OUTCOME_PASS,
            'io_log': ((0, 'stdout', "attr: value\n"),)
        })
        jobstate = JobState(self.job_R)
        jobstate.result = result_R
        jobstate_enc = jobstate._get_persistance_subset()
        # The inhibitor list is not saved
        with self.assertRaises(KeyError):
            jobstate_enc['_readiness_inhibitor_list']
        # Resource have to be re evealutated on startup, outcome of the job
        # must be reset to JobResult.OUTCOME_NONE
        self.assertEqual(jobstate_enc['_result'].outcome,
                         JobResult.OUTCOME_NONE)

    def test_encode_normal_job(self):
        result = JobResult({
            'job': self.job,
            'outcome': JobResult.OUTCOME_PASS,
        })
        self.job_state.result = result
        jobstate_enc = self.job_state._get_persistance_subset()
        # The inhibitor list is not saved
        with self.assertRaises(KeyError):
            jobstate_enc['_readiness_inhibitor_list']
        # Normal jobs should keep their outcome value
        self.assertEqual(jobstate_enc['_result'].outcome,
                         JobResult.OUTCOME_PASS)

    def test_decode(self):
        raw_json = """{
            "_class_id": "JOB_STATE",
            "_job": {
                "_class_id": "JOB_DEFINITION",
                "data": {
                    "name": "X",
                    "plugin": "dummy"
                }
            },
            "_result": {
                "_class_id": "JOB_RESULT",
                "data": {
                    "comments": null,
                    "job": {
                        "_class_id": "JOB_DEFINITION",
                        "data": {
                            "name": "X",
                            "plugin": "dummy"
                        }
                    },
                    "outcome": "pass",
                    "return_code": null
                }
            }
        }"""
        job_dec = json.loads(raw_json,
            object_hook=SessionStateEncoder().dict_to_object)
        self.assertIsInstance(job_dec, JobState)
        self.assertEqual(repr(job_dec._result),
            ("<JobResult job:<JobDefinition name:'X'"
             " plugin:'dummy'> outcome:'pass'>"))


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

    def test_initial_session_dir(self):
        self.assertIsNone(self.session_state.session_dir)


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
        self.job_list = [self.job_A, self.job_R, self.job_X, self.job_Y]
        self.session = SessionState(self.job_list)
        self.scratch_dir = TemporaryDirectory()

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
        result_R = JobResult({
            'job': self.job_R,
            'io_log': make_io_log(((0, 'stdout', b"attr: value\n"),),
                                  self.scratch_dir)
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
        result_A = JobResult({'job': self.job_A})
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
        result_R = JobResult({
            'job': self.job_R,
            'io_log': make_io_log((
                    (0, 'stdout', b"attr: value-1\n"),
                    (1, 'stdout', b"\n"),
                    (1, 'stdout', b"I-sound-like-a-broken-record\n"),
                    (1, 'stdout', b"\n"),
                    (1, 'stdout', b"attr: value-2\n")),
                self.scratch_dir)
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
        result_Y = JobResult({
            'job': self.job_Y,
            'outcome': JobResult.OUTCOME_FAIL
        })
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
        result_Y = JobResult({
            'job': self.job_Y,
            'outcome': JobResult.OUTCOME_PASS
        })
        self.session.update_job_result(self.job_Y, result_Y)
        # Now X is runnable
        self.assertEqual(self.job_state('X').readiness_inhibitor_list, [])
        self.assertTrue(self.job_state('X').can_start())

    def test_desired_job_X_cannot_run_with_no_resource_R(self):
        # A variant of the two test cases above, using A-R jobs
        self.session.update_desired_job_list([self.job_A])
        result_R = JobResult({
            'job': self.job_R,
            'io_log': make_io_log(((0, 'stdout', b'attr: wrong value\n'),),
                                  self.scratch_dir)
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
        result_R_old = JobResult({
            'job': self.job_R,
            'io_log': make_io_log(((0, 'stdout', b"attr: old value\n"),),
                                  self.scratch_dir)
        })
        self.session.update_job_result(self.job_R, result_R_old)
        # So here the old result is stored into a new 'R' resource
        expected_before = {'R': [Resource({'attr': 'old value'})]}
        self.assertEqual(self.session._resource_map, expected_before)
        # Now we present the second result for the same job
        result_R_new = JobResult({
            'job': self.job_R,
            'io_log': make_io_log(((0, 'stdout', b"attr: new value\n"),),
                                  self.scratch_dir)
        })
        self.session.update_job_result(self.job_R, result_R_new)
        # What should happen here is that the R resource is entirely replaced
        # by the data from the new result. The data should not be merged or
        # appended in any way.
        expected_after = {'R': [Resource({'attr': 'new value'})]}
        self.assertEqual(self.session._resource_map, expected_after)

    # TODO: add tests for local jobs

    def tearDown(self):
        self.scratch_dir.cleanup()


class SessionStateLocalStorageTests(TestCase):

    def setUp(self):
        # session data are kept in XDG_CACHE_HOME/plainbox/.session
        # To avoid resuming a real session, we have to select a temporary
        # location instead
        self._sandbox = tempfile.mkdtemp()
        self._env = os.environ
        os.environ['XDG_CACHE_HOME'] = self._sandbox

    def job_state(self, name):
        # A helper function to avoid overly long expressions
        return self.session.job_state_map[name]

    def test_persistent_save(self):
        self.job_A = make_job("A")
        self.job_list = [self.job_A]
        self.session = SessionState(self.job_list)
        result_A = JobResult({
            'job': self.job_A,
            'outcome': JobResult.OUTCOME_PASS,
            'comments': 'All good',
            'return_code': 0,
            'io_log': ((0, 'stdout', "Success !\n"),)
        })
        session_json_text = """{
            "_job_state_map": {
                "A": {
                    "_job": {
                        "data": {
                            "name": "A",
                            "plugin": "dummy",
                            "requires": null,
                            "depends": null
                        },
                        "_class_id": "JOB_DEFINITION"
                    },
                    "_result": {
                        "data": {
                            "job": {
                                "data": {
                                    "name": "A",
                                    "plugin": "dummy",
                                    "requires": null,
                                    "depends": null
                                },
                                "_class_id": "JOB_DEFINITION"
                            },
                            "outcome": "pass",
                            "return_code": 0,
                            "comments": "All good",
                            "io_log": [
                                [
                                    0,
                                    "stdout",
                                    "Success !\\n"
                                ]
                            ]
                        },
                        "_class_id": "JOB_RESULT"
                    },
                    "_class_id": "JOB_STATE"
                }
            },
            "_desired_job_list": [
                {
                    "data": {
                        "name": "A",
                        "plugin": "dummy",
                        "requires": null,
                        "depends": null
                    },
                    "_class_id": "JOB_DEFINITION"
                }
            ],
            "_class_id": "SESSION_STATE"
        }"""
        self.session.open()
        self.session.update_desired_job_list([self.job_A])
        self.session.update_job_result(self.job_A, result_A)
        self.session.persistent_save()
        session_file = self.session.previous_session_file()
        self.session.close()
        self.assertIsNotNone(session_file)
        with open(session_file) as f:
            raw_json = json.load(f)
            self.maxDiff = None
            self.assertEqual(raw_json, json.loads(session_json_text))

    def test_resume_session(self):
        # All of the tests below are using one session. The session has four
        # jobs, Job A depends on a resource provided by job R which has no
        # dependencies at all. Both Job X and Y depend on job A.
        #
        # A -(resource dependency)-> R
        #
        # X -(direct dependency) -> A
        #
        # Y -(direct dependency) -> A
        self.job_A = make_job("A", requires="R.attr == 'value'")
        self.job_A_expr = self.job_A.get_resource_program().expression_list[0]
        self.job_R = make_job("R", plugin="resource")
        self.job_X = make_job("X", depends='A')
        self.job_Y = make_job("Y", depends='A')
        self.job_list = [self.job_A, self.job_R, self.job_X, self.job_Y]
        # Create a new session (session_dir is empty)
        self.session = SessionState(self.job_list)
        result_R = JobResult({
            'job': self.job_R,
            'io_log': make_io_log(((0, 'stdout', b"attr: value\n"),),
                                  self._sandbox)
        })
        result_A = JobResult({
            'job': self.job_A,
            'outcome': JobResult.OUTCOME_PASS
        })
        result_X = JobResult({
            'job': self.job_X,
            'outcome': JobResult.OUTCOME_PASS
        })
        # Job Y can't start as it requires job A
        self.assertFalse(self.job_state('Y').can_start())
        self.session.update_desired_job_list([self.job_X, self.job_Y])
        self.session.open()
        self.session.update_job_result(self.job_R, result_R)
        self.session.update_job_result(self.job_A, result_A)
        self.session.update_job_result(self.job_X, result_X)
        self.session.persistent_save()
        self.session.close()
        # Create a new session (session_dir should contain session data)
        self.session = SessionState(self.job_list)
        self.session.open()
        # Resume the previous session
        self.session.resume()
        # This time job Y can start
        self.assertTrue(self.job_state('Y').can_start())
        self.session.close()

    def tearDown(self):
        shutil.rmtree(self._sandbox)
        os.environ = self._env
