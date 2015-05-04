# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <daniel.manrique@canonical.com>
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
plainbox.impl.exporter.test_html
================================

Test definitions for plainbox.impl.exporter.html module
"""
from unittest import TestCase
import io

from plainbox.abc import IJobResult
from plainbox.testing_utils import resource_string
from plainbox.impl.exporter.html import HTMLSessionStateExporter
from plainbox.impl.resource import Resource
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.unit.job import JobDefinition
from plainbox.vendor import mock


class HTMLExporterTests(TestCase):

    def setUp(self):
        self.resource_map = {
            '2013.com.canonical.certification::lsb': [
                Resource({'description': 'Ubuntu 14.04 LTS'})],
            '2013.com.canonical.certification::package': [
                Resource({'name': 'plainbox', 'version': '1.0'}),
                Resource({'name': 'fwts', 'version': '0.15.2'})],
        }
        self.job1 = JobDefinition({'id': 'job_id1', '_summary': 'job 1'})
        self.job2 = JobDefinition({'id': 'job_id2', '_summary': 'job 2'})
        self.job3 = JobDefinition({'id': 'job_id3', '_summary': 'job 3'})
        self.result_fail = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_FAIL, 'return_code': 1,
            'io_log': [(0, 'stderr', b'FATAL ERROR\n')],
        })
        self.result_pass = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS, 'return_code': 0,
            'io_log': [(0, 'stdout', b'foo\n')],
            'comments': 'blah blah'
        })
        self.result_skip = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_SKIP,
            'comments': 'No such device'
        })
        self.attachment = JobDefinition({
            'id': 'dmesg_attachment',
            'plugin': 'attachment'})
        self.attachment_result = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'io_log': [(0, 'stdout', b'bar\n')],
            'return_code': 0
        })

    def prepare_manager_without_certification_status(self):
        return mock.Mock(state=mock.Mock(
            job_state_map={
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='unspecified'),
                self.job2.id: mock.Mock(
                    result=self.result_pass,
                    job=self.job2,
                    effective_certification_status='unspecified'),
                self.job3.id: mock.Mock(
                    result=self.result_skip,
                    job=self.job3,
                    effective_certification_status='unspecified'),
                self.attachment.id: mock.Mock(result=self.attachment_result,
                                              job=self.attachment)
            },
            get_certification_status_map=mock.Mock(return_value={}),
            resource_map=self.resource_map)
        )

    def prepare_manager_with_certification_blocker(self):
        return mock.Mock(state=mock.Mock(
            job_state_map={
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='blocker'),
                self.job2.id: mock.Mock(
                    result=self.result_pass,
                    job=self.job2,
                    effective_certification_status='unspecified'),
                self.job3.id: mock.Mock(
                    result=self.result_skip,
                    job=self.job3,
                    effective_certification_status='unspecified'),
                self.attachment.id: mock.Mock(result=self.attachment_result,
                                              job=self.attachment)
            },
            get_certification_status_map=mock.Mock(side_effect=[{
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='blocker')},{
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='blocker')}]),
            resource_map=self.resource_map)
        )

    def prepare_manager_with_certification_non_blocker(self):
        return mock.Mock(state=mock.Mock(
            job_state_map={
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='non-blocker'),
                self.job2.id: mock.Mock(
                    result=self.result_pass,
                    job=self.job2,
                    effective_certification_status='unspecified'),
                self.job3.id: mock.Mock(
                    result=self.result_skip,
                    job=self.job3,
                    effective_certification_status='unspecified'),
                self.attachment.id: mock.Mock(result=self.attachment_result,
                                              job=self.attachment)
            },
            get_certification_status_map=mock.Mock(side_effect=[{},{
                self.job2.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='non-blocker')},{
                self.job2.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='non-blocker')}]),
            resource_map=self.resource_map)
        )

    def prepare_manager_with_both_certification_status(self):
        return mock.Mock(state=mock.Mock(
            job_state_map={
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='blocker'),
                self.job2.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job2,
                    effective_certification_status='non-blocker'),
                self.job3.id: mock.Mock(
                    result=self.result_skip,
                    job=self.job3,
                    effective_certification_status='unspecified'),
                self.attachment.id: mock.Mock(result=self.attachment_result,
                                              job=self.attachment)
            },
            get_certification_status_map=mock.Mock(side_effect=[{
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='blocker')},{
                self.job1.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job1,
                    effective_certification_status='blocker')},{
                self.job2.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job2,
                    effective_certification_status='non-blocker')},{
                self.job2.id: mock.Mock(
                    result=self.result_fail,
                    job=self.job2,
                    effective_certification_status='non-blocker')}]),
            resource_map=self.resource_map)
        )

    def test_perfect_match_without_certification_status(self):
        """
        Test that output from the exporter exactly matches known
        good HTML output, inlining and everything included.
        """
        exporter = HTMLSessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0")
        stream = io.BytesIO()
        exporter.dump_from_session_manager(
            self.prepare_manager_without_certification_status(), stream)
        actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(actual_result, bytes)
        expected_result = resource_string(
            "plainbox",
            "test-data/html-exporter/without_certification_status.html"
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(actual_result, expected_result)

    def test_perfect_match_with_certification_blocker(self):
        """
        Test that output from the exporter exactly matches known
        good HTML output, inlining and everything included.
        """
        exporter = HTMLSessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0")
        stream = io.BytesIO()
        exporter.dump_from_session_manager(
            self.prepare_manager_with_certification_blocker(), stream)
        actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(actual_result, bytes)
        expected_result = resource_string(
            "plainbox",
            "test-data/html-exporter/with_certification_blocker.html"
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(actual_result, expected_result)

    def test_perfect_match_with_certification_non_blocker(self):
        """
        Test that output from the exporter exactly matches known
        good HTML output, inlining and everything included.
        """
        exporter = HTMLSessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0")
        stream = io.BytesIO()
        exporter.dump_from_session_manager(
            self.prepare_manager_with_certification_non_blocker(), stream)
        actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(actual_result, bytes)
        expected_result = resource_string(
            "plainbox",
            "test-data/html-exporter/with_certification_non_blocker.html"
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(actual_result, expected_result)

    def test_perfect_match_with_both_certification_status(self):
        """
        Test that output from the exporter exactly matches known
        good HTML output, inlining and everything included.
        """
        exporter = HTMLSessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0")
        stream = io.BytesIO()
        exporter.dump_from_session_manager(
            self.prepare_manager_with_both_certification_status(), stream)
        actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(actual_result, bytes)
        expected_result = resource_string(
            "plainbox",
            "test-data/html-exporter/with_both_certification_status.html"
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(actual_result, expected_result)
