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
from unittest import TestCase, expectedFailure

from plainbox.abc import IJobResult
from plainbox.impl.session import InhibitionCause
from plainbox.impl.session import JobReadinessInhibitor
from plainbox.impl.session import JobState
from plainbox.impl.session import UndesiredJobReadinessInhibitor
from plainbox.impl.testing_utils import make_job, make_job_result


def load_tests(loader, tests, ignore):
    tests.addTests(DocTestSuite(
        'plainbox.impl.session.jobs', optionflags=REPORT_NDIFF))
    return tests


class JobReadinessInhibitorTests(TestCase):

    def test_bad_initialization(self):
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.UNDESIRED - 1)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.FAILED_RESOURCE + 1)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.PENDING_DEP)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.FAILED_DEP)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.PENDING_RESOURCE)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.FAILED_RESOURCE)
        job = make_job("A")
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.PENDING_RESOURCE, job)
        self.assertRaises(ValueError, JobReadinessInhibitor,
                          InhibitionCause.FAILED_RESOURCE, job)

    def test_unknown(self):
        obj = JobReadinessInhibitor(InhibitionCause.UNDESIRED)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:UNDESIRED"
                " related_job:None"
                " related_expression:None>"))
        self.assertEqual(str(obj), "undesired")

    def test_pending_dep(self):
        job = make_job("A")
        obj = JobReadinessInhibitor(
            InhibitionCause.PENDING_DEP, related_job=job)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:PENDING_DEP"
                " related_job:<JobDefinition id:'A' plugin:'dummy'>"
                " related_expression:None>"))
        self.assertEqual(str(obj), "required dependency 'A' did not run yet")

    def test_failed_dep(self):
        job = make_job("A")
        obj = JobReadinessInhibitor(
            InhibitionCause.FAILED_DEP, related_job=job)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:FAILED_DEP"
                " related_job:<JobDefinition id:'A' plugin:'dummy'>"
                " related_expression:None>"))
        self.assertEqual(str(obj), "required dependency 'A' has failed")

    def test_pending_resource(self):
        job = make_job("A", requires="resource.attr == 'value'")
        expr = job.get_resource_program().expression_list[0]
        obj = JobReadinessInhibitor(
            InhibitionCause.PENDING_RESOURCE, related_job=job,
            related_expression=expr)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:PENDING_RESOURCE"
                " related_job:<JobDefinition id:'A' plugin:'dummy'>"
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
            InhibitionCause.FAILED_RESOURCE, related_job=job,
            related_expression=expr)
        self.assertEqual(
            repr(obj), (
                "<JobReadinessInhibitor cause:FAILED_RESOURCE"
                " related_job:<JobDefinition id:'A' plugin:'dummy'>"
                " related_expression:"
                "<ResourceExpression text:\"resource.attr == 'value'\">>"))
        self.assertEqual(
            str(obj), (
                "resource expression \"resource.attr == 'value'\""
                " evaluates to false"))

    def test_unknown_global(self):
        self.assertEqual(UndesiredJobReadinessInhibitor.cause,
                         InhibitionCause.UNDESIRED)


class JobStateTests(TestCase):

    def setUp(self):
        self.job = make_job("A")
        self.job_state = JobState(self.job)

    def test_smoke(self):
        self.assertIsNotNone(self.job_state.result)
        self.assertIs(self.job_state.result.outcome, IJobResult.OUTCOME_NONE)
        self.assertEqual(self.job_state.result_history, ())
        self.assertEqual(self.job_state.readiness_inhibitor_list, [
            UndesiredJobReadinessInhibitor])
        self.assertEqual(self.job_state.effective_category_id,
                         self.job.category_id)
        self.assertEqual(self.job_state.effective_certification_status,
                         self.job.certification_status)
        self.assertIsNone(self.job_state.via_job)

    def test_getting_job(self):
        self.assertIs(self.job_state.job, self.job)

    @expectedFailure
    def test_setting_job_is_not_allowed(self):
        # FIXME: We want this test to come back at some point so I didn't
        # delete it, but at the moment we need it to always pass because
        # a JobState's job attribute needs to be writable.
        with self.assertRaises(AttributeError):
            self.job_state.job = None

    def test_setting_result(self):
        result = make_job_result()
        self.job_state.result = result
        self.assertIs(self.job_state.result, result)

    def test_result_history_keeps_track_of_result_changes(self):
        # XXX: this example will fail if subsequent results are identical
        self.assertEqual(self.job_state.result_history, ())
        result1 = make_job_result(outcome='fail')
        self.job_state.result = result1
        self.assertEqual(self.job_state.result_history, (result1,))
        result2 = make_job_result(outcome='pass')
        self.job_state.result = result2
        self.assertEqual(self.job_state.result_history, (result1, result2))

    def test_setting_result_fires_signal(self):
        """
        verify that assigning state.result fires the on_result_changed signal
        """
        # Remember both new and old result for verification
        new_result = make_job_result()
        old_result = self.job_state.result

        def changed_callback(old, new):
            # Verify that new and old are correct and not swapped
            self.assertIs(new, new_result)
            self.assertIs(old, old_result)
            # Set a flag that we verify below in case this never gets called
            self.on_changed_fired = True
        # Connect the signal handler
        self.job_state.on_result_changed.connect(changed_callback)
        # Assign the new result
        self.job_state.result = new_result
        # Ensure that the signal was fired and called our callback
        self.assertTrue(self.on_changed_fired)

    def test_setting_result_fires_signal_only_when_real_change_happens(self):
        """
        verify that assigning state.result does NOT fire the signal when the
        new result is the same
        """
        # Assume we never get called and reset the flag
        self.on_changed_fired = False

        def changed_callback(old, new):
            # Set the flag in case we do get called
            self.on_changed_fired = True
        # Connect the signal handler
        self.job_state.on_result_changed.connect(changed_callback)
        # Assign the same result again
        self.job_state.result = self.job_state.result
        # Ensure that the signal was NOT fired
        self.assertFalse(self.on_changed_fired)

    def test_setting_readiness_inhibitor_list(self):
        inhibitor = JobReadinessInhibitor(InhibitionCause.UNDESIRED)
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

    def test_setting_effective_category_id(self):
        self.job_state.effective_category_id = 'value'
        self.assertEqual(self.job_state.effective_category_id, 'value')

    def test_setting_effective_cert_certification_status(self):
        self.job_state.effective_certification_status = 'value'
        self.assertEqual(self.job_state.effective_certification_status,
                         'value')

    def test_setting_via_job__TypeError(self):
        with self.assertRaises(TypeError):
            self.job_state.via_job = 'value'

    def test_setting_via_job(self):
        parent = make_job("parent")
        self.job_state.via_job = parent
        self.assertIs(self.job_state.via_job, parent)

    def test_resetting_via_job(self):
        parent = make_job("parent")
        self.job_state.via_job = parent
        self.assertIs(self.job_state.via_job, parent)
        self.job_state.via_job = None
        self.assertIs(self.job_state.via_job, None)
