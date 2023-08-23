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

from unittest import TestCase, mock
from functools import partial

from checkbox_ng.launcher.merge_submissions import MergeSubmissions


class MergeSubmissionsTests(TestCase):
    @mock.patch("checkbox_ng.launcher.merge_submissions.TemporaryDirectory")
    @mock.patch("checkbox_ng.launcher.merge_submissions.SessionManager")
    @mock.patch("checkbox_ng.launcher.merge_submissions.MergeReports")
    @mock.patch("builtins.print")
    @mock.patch("tarfile.open")
    @mock.patch("json.load")
    # used to load an empty launcher with no error
    def test_invoked_ok(
        self,
        json_mock,
        tarfile_mock,
        print_mock,
        merge_reports_mock,
        session_manager_mock,
        temporary_directory_mock,
    ):
        ctx_mock = mock.MagicMock()
        ctx_mock.args.submission = ["submission"]
        ctx_mock.args.output_file = "file_location"

        self_mock = mock.MagicMock()

        with mock.patch("builtins.open"):
            MergeSubmissions.invoked(self_mock, ctx_mock)

        # output path was printed
        print_mock.assert_any_call(ctx_mock.args.output_file)
