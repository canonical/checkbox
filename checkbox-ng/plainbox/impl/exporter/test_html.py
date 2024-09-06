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

from pkg_resources import resource_string

from plainbox.abc import IJobResult
from plainbox.impl.exporter.jinja2 import Jinja2SessionStateExporter
from plainbox.impl.providers import get_providers
from plainbox.impl.providers.special import get_categories
from plainbox.impl.resource import Resource
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session import SessionManager
from plainbox.impl.unit.exporter import ExporterUnitSupport
from plainbox.impl.unit.job import JobDefinition


class HTMLExporterTests(TestCase):
    """Tests for Jinja2SessionStateExporter using the HTML template."""

    def setUp(self):
        self.exporter_unit = self._get_all_exporter_units()[
            "com.canonical.plainbox::html"
        ]
        self.resource_map = {
            "com.canonical.certification::lsb": [
                Resource({"description": "Ubuntu 14.04 LTS"})
            ],
            "com.canonical.certification::package": [
                Resource({"name": "plainbox", "version": "1.0"}),
                Resource({"name": "fwts", "version": "0.15.2"}),
            ],
        }
        self.job1 = JobDefinition({"id": "job_id1", "_summary": "job 1"})
        self.job2 = JobDefinition({"id": "job_id2", "_summary": "job 2"})
        self.job3 = JobDefinition({"id": "job_id3", "_summary": "job 3"})
        self.res1 = JobDefinition(
            {"id": "lsb", "plugin": "resource", "_summary": "lsb"}
        )
        self.res2 = JobDefinition(
            {"id": "package", "plugin": "resource", "_summary": "package"}
        )
        self.result_fail = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_FAIL,
                "return_code": 1,
                "io_log": [(0, "stderr", b"FATAL ERROR\n")],
            }
        )
        self.result_pass = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "return_code": 0,
                "io_log": [(0, "stdout", b"foo\n")],
                "comments": "blah blah",
            }
        )
        self.result_skip = MemoryJobResult(
            {"outcome": IJobResult.OUTCOME_SKIP, "comments": "No such device"}
        )
        self.attachment = JobDefinition(
            {"id": "dmesg_attachment", "plugin": "attachment"}
        )
        self.attachment_result = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "io_log": [(0, "stdout", b"bar\n")],
                "return_code": 0,
            }
        )
        self.res1_result = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "io_log": [(0, "stdout", b"description: Ubuntu 14.04 LTS\n")],
                "return_code": 0,
            }
        )
        self.res2_result = MemoryJobResult(
            {
                "outcome": IJobResult.OUTCOME_PASS,
                "io_log": [
                    (0, "stdout", b"name: plainbox\n"),
                    (1, "stdout", b"version: 1.0\n"),
                    (2, "stdout", b"\n"),
                    (3, "stdout", b"name: fwts\n"),
                    (4, "stdout", b"version: 0.15.2\n"),
                ],
                "return_code": 0,
            }
        )
        self.session_manager = SessionManager.create()
        self.session_manager.add_local_device_context()
        self.session_state = self.session_manager.default_device_context.state
        session_state = self.session_state
        session_state.add_unit(self.job1)
        session_state.add_unit(self.job2)
        session_state.add_unit(self.job3)
        session_state.add_unit(self.res1)
        session_state.add_unit(self.res2)
        session_state.add_unit(self.attachment)
        for unit in get_categories().unit_list:
            session_state.add_unit(unit)
        session_state.update_job_result(self.job1, self.result_fail)
        session_state.update_job_result(self.job2, self.result_pass)
        session_state.update_job_result(self.job3, self.result_skip)
        session_state.update_job_result(self.res1, self.res1_result)
        session_state.update_job_result(self.res2, self.res2_result)
        session_state.update_job_result(
            self.attachment, self.attachment_result
        )
        for resource_id, resource_list in self.resource_map.items():
            session_state.set_resource_list(resource_id, resource_list)

    def tearDown(self):
        self.session_manager.destroy()

    def _get_session_manager(
        self, job1_cert_status, job2_cert_status, job3_cert_status
    ):
        session_state = self.session_manager.default_device_context.state
        job1_state = session_state.job_state_map[self.job1.id]
        job2_state = session_state.job_state_map[self.job2.id]
        job3_state = session_state.job_state_map[self.job3.id]
        job1_state.effective_certification_status = job1_cert_status
        job2_state.effective_certification_status = job2_cert_status
        job3_state.effective_certification_status = job3_cert_status
        return self.session_manager

    def _get_all_exporter_units(self):
        exporter_map = {}
        for provider in get_providers():
            for unit in provider.unit_list:
                if unit.Meta.name == "exporter":
                    exporter_map[unit.id] = ExporterUnitSupport(unit)
        return exporter_map

    def prepare_manager_without_certification_status(self):
        return self._get_session_manager(
            "non-blocker", "non-blocker", "non-blocker"
        )

    def prepare_manager_with_certification_blocker(self):
        return self._get_session_manager(
            "blocker", "non-blocker", "non-blocker"
        )

    def test_perfect_match_without_certification_status(self):
        """
        Test that output from the exporter exactly matches known
        good HTML output, inlining and everything included.
        """
        exporter = Jinja2SessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="Checkbox 1.0",
            exporter_unit=self.exporter_unit,
        )
        stream = io.BytesIO()
        exporter.dump_from_session_manager(
            self.prepare_manager_without_certification_status(), stream
        )
        actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(actual_result, bytes)
        expected_result = resource_string(
            "plainbox",
            "test-data/html-exporter/without_certification_status.html",
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(actual_result, expected_result)

    def test_perfect_match_with_certification_blocker(self):
        """
        Test that output from the exporter exactly matches known
        good HTML output, inlining and everything included.
        """
        exporter = Jinja2SessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="Checkbox 1.0",
            exporter_unit=self.exporter_unit,
        )
        stream = io.BytesIO()
        exporter.dump_from_session_manager(
            self.prepare_manager_with_certification_blocker(), stream
        )
        actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(actual_result, bytes)
        expected_result = resource_string(
            "plainbox",
            "test-data/html-exporter/with_certification_blocker.html",
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(actual_result, expected_result)
