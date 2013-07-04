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

import json

from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session import JobReadinessInhibitor
from plainbox.impl.session import JobState
from plainbox.impl.session import SessionStateEncoder
from plainbox.impl.session import UndesiredJobReadinessInhibitor
from plainbox.impl.testing_utils import make_job, make_job_result


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
        self.assertIs(self.job_state.result.outcome, IJobResult.OUTCOME_NONE)
        self.assertEqual(self.job_state.readiness_inhibitor_list, [
            UndesiredJobReadinessInhibitor])

    def test_getting_job(self):
        self.assertIs(self.job_state.job, self.job)

    def test_setting_job_is_not_allowed(self):
        with self.assertRaises(AttributeError):
            self.job_state.job = None

    def test_setting_result(self):
        result = make_job_result()
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
        result_R = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'io_log': ((0, 'stdout', "attr: value\n"),)
        })
        jobstate = JobState(self.job_R)
        jobstate.result = result_R
        jobstate_enc = jobstate._get_persistance_subset()
        # The inhibitor list is not saved
        with self.assertRaises(KeyError):
            jobstate_enc['_readiness_inhibitor_list']
        # Resource have to be re evealutated on startup, outcome of the job
        # must be reset to IJobResult.OUTCOME_NONE
        self.assertEqual(
            jobstate_enc['_result'].outcome,
            IJobResult.OUTCOME_NONE)

    def test_encode_normal_job(self):
        result = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
        })
        self.job_state.result = result
        jobstate_enc = self.job_state._get_persistance_subset()
        # The inhibitor list is not saved
        with self.assertRaises(KeyError):
            jobstate_enc['_readiness_inhibitor_list']
        # Normal jobs should keep their outcome value
        self.assertEqual(jobstate_enc['_result'].outcome,
                         IJobResult.OUTCOME_PASS)

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
                "_class_id": "JOB_RESULT(m)",
                "data": {
                    "comments": null,
                    "outcome": "pass",
                    "return_code": null
                }
            }
        }"""
        job_dec = json.loads(
            raw_json, object_hook=SessionStateEncoder().dict_to_object)
        self.assertIsInstance(job_dec, JobState)
        self.assertEqual(
            repr(job_dec._result), "<MemoryJobResult outcome:'pass'>")
