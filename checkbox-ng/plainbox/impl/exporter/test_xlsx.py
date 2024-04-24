# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

from collections import OrderedDict
from unittest import TestCase
from unittest.mock import MagicMock, ANY

from plainbox.impl.exporter.xlsx import XLSXSessionStateExporter
from plainbox.impl.session import SessionState
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.category import CategoryUnit


class XLSXSessionStateExporterTests(TestCase):
    def test_write_job(self):
        self_mock = MagicMock()
        # tree = {"Uncategorised": {"job1": {}}}
        tree = {"job1": {}}
        result_map = {
            "job1": OrderedDict(
                [
                    ("summary", "job1"),
                    ("category_id", "com.canonical.plainbox::uncategorised"),
                    ("outcome", "pass"),
                    ("plugin", "shell"),
                    ("io_log", ""),
                    ("comments", ""),
                    ("command", 'echo "This is job1"'),
                    ("certification_status", "non-blocker"),
                ]
            ),
            "Uncategorised": {
                "category_status": "pass",
                "plugin": "local",
                "summary": "Uncategorised",
            },
        }
        XLSXSessionStateExporter._write_job(self_mock, tree, result_map, 2)
        # self_mock.worksheet3.write.assert_called()
        self_mock.worksheet3.write.assert_any_call(ANY, ANY, "", ANY)
        # self_mock.worksheet3.write.assert_called_with(ANY, ANY, "", ANY)
        # self.assertEqual(self_mock.worksheet3.write.call_count, 2)

    def test_category_map(self):
        self_mock = MagicMock()
        A = JobDefinition({"id": "A", "category_id": "test"})
        B = JobDefinition({"id": "B", "certification-status": "blocker"})
        job_list = [A, B]
        unit = MagicMock(name="unit", spec_set=CategoryUnit)
        unit.id = "test"
        unit.tr_name.return_value = "Test"
        unit.Meta.name = "category"

        state = SessionState(job_list)
        state.update_desired_job_list(job_list)
        state.unit_list.append(unit)

        self.assertEqual(
            XLSXSessionStateExporter._category_map(self_mock, state),
            {"test": "Test"},
        )

    def test_write_tp_export(self):
        self_mock = MagicMock()
        self_mock._category_map.return_value = {
            "com.canonical.plainbox::uncategorised": "test"
        }
        data = MagicMock()
        A = JobDefinition({"id": "A"})
        B = JobDefinition({"id": "B", "certification-status": "blocker"})
        job_list = [A, B]
        unit = MagicMock(name="unit", spec_set=CategoryUnit)
        unit.Meta.name = "category"

        state = SessionState(job_list)
        data["manager"].default_device_context.state = state
        XLSXSessionStateExporter.write_tp_export(self_mock, data)
        self_mock.worksheet4.write_row.assert_called_with(
            ANY, 0, ["test", "", ""], ANY
        )
        state.update_desired_job_list(job_list)
        state.unit_list.append(unit)

        data["manager"].default_device_context.state = state
        XLSXSessionStateExporter.write_tp_export(self_mock, data)
        self_mock.worksheet4.write_row.assert_any_call(
            ANY, 0, ["A", "", "A"], ANY
        )
        self_mock.worksheet4.write_row.assert_any_call(
            ANY, 0, ["B", "blocker", "B"], ANY
        )
