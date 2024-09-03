# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

from unittest import TestCase
from unittest.mock import patch, MagicMock
from functools import partial

from checkbox_ng.launcher.merge_reports import MergeReports


class MergeReportsTests(TestCase):
    @patch("checkbox_ng.launcher.merge_reports.TemporaryDirectory")
    @patch("checkbox_ng.launcher.merge_reports.SessionManager")
    @patch("checkbox_ng.launcher.merge_reports.JobDefinition")
    @patch("checkbox_ng.launcher.merge_reports.CategoryUnit")
    @patch("builtins.print")
    @patch("os.path.join")
    @patch("tarfile.open")
    @patch("json.load")
    # used to load an empty launcher with no error
    def test_invoked_ok(
        self,
        json_mock,
        tarfile_mock,
        path_join_mock,
        print_mock,
        category_mock,
        job_definition_mock,
        session_manager_mock,
        temp_dir_mock,
    ):
        ctx_mock = MagicMock()
        ctx_mock.args.submission = ["submission"]
        ctx_mock.args.output_file = "file_location"

        self_mock = MagicMock()
        self_mock._parse_submission = partial(
            MergeReports._parse_submission, self_mock
        )

        basic_job_info = {
            "name": "test_name",
            "id": "test_id",  # note: no :: to fetch the default ns
        }
        sub_to_read = {
            "title": "report title",
            "results": [basic_job_info],
            "resource-results": [basic_job_info],
            "attachment-results": [basic_job_info],
            "category_map": {"test_category": "test_name"},
        }
        json_mock.return_value = sub_to_read

        with patch("builtins.open"):
            MergeReports.invoked(self_mock, ctx_mock)

        # output path was printed
        print_mock.assert_any_call(ctx_mock.args.output_file)
        exporter = self_mock._create_exporter.return_value
        # exporter was created and dumped
        self.assertTrue(exporter.dump_from_session_manager_list.called)

    def test_populate_session_state(self):
        job_mock = MagicMock()
        state_mock = MagicMock()
        self_mock = MagicMock()
        MergeReports._populate_session_state(self_mock, job_mock, state_mock)
        self.assertTrue(job_mock.get_record_value.called)
