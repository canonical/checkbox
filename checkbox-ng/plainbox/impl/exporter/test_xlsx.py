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
