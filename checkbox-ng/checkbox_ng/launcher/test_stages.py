# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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


from pathlib import Path
from unittest import TestCase, mock

from checkbox_ng.launcher.stages import MainLoopStage, ReportsStage


class TestMainLoopStage(TestCase):
    def test__run_single_job_with_ui_loop_quit(self):
        self_mock = mock.MagicMock()
        job_mock = mock.MagicMock()
        ui_mock = mock.MagicMock()
        job_state_mock = mock.MagicMock()

        job_mock.id = "job_id"
        job_mock.plugin = "user-interact"
        self_mock.sa.get_job_state.return_value = job_state_mock
        job_state_mock.can_start.return_value = True

        ui_mock.wait_for_interaction_prompt.return_value = "quit"

        with self.assertRaises(SystemExit):
            MainLoopStage._run_single_job_with_ui_loop(
                self_mock, job_mock, ui_mock
            )

    def test__run_single_job_with_ui_loop_quit_skip_comment(self):
        self_mock = mock.MagicMock()
        job_mock = mock.MagicMock()
        ui_mock = mock.MagicMock()
        job_state_mock = mock.MagicMock()

        job_mock.id = "job_id"
        job_mock.plugin = "user-interact"
        self_mock.sa.get_job_state.return_value = job_state_mock
        self_mock.is_interactive = True
        job_state_mock.can_start.return_value = True
        job_state_mock.effective_certification_status = "not_blocker"

        # Sequence of user actions: first "comment", then "skip"
        ui_mock.wait_for_interaction_prompt.side_effect = ["comment", "skip"]
        # Simulate user entering a comment after being prompted
        with mock.patch("builtins.input", return_value="Test comment"):
            result_builder = MainLoopStage._run_single_job_with_ui_loop(
                self_mock, job_mock, ui_mock
            )

        self.assertEqual(result_builder.outcome, "skip")


class TestReportsStage(TestCase):
    def test__get_submission_file_path(self):
        # LP:1585326 maintain isoformat but removing ':' chars that cause
        # issues when copying files.
        self_mock = mock.MagicMock()
        self_mock.base_dir = "~/.some_path"

        path = ReportsStage._get_submission_file_path(self_mock, ".tmp")
        self.assertNotIn(path, ":")

    def test__export_results_c3_prints_also_to_file(self):
        """
        That the the c3 exporter also reports back the C3 submission url after
        submitting
        """
        self_mock = mock.MagicMock()
        self_mock.is_interactive = False
        config_mock = self_mock.sa.config
        config_mock.get_value.return_value = "none"

        def get_parametric_sections(section):
            if section == "report":
                return {"c3": {"exporter": "tar", "transport": "c3"}}
            elif section == "exporter":
                return {"tar": {"unit": "some_id"}}
            return {}

        config_mock.get_parametric_sections = get_parametric_sections
        self_mock._export_fn = None
        self_mock.sa.export_to_transport.return_value = {
            "status_url": "https://certification.canonical.com/submissions/status/EXAMPLE"
        }
        mock_open = mock.mock_open()
        with mock.patch("checkbox_ng.launcher.stages.open", mock_open) as f:
            ReportsStage._export_results(self_mock)
            file_mock = f.return_value
            self.assertTrue(file_mock.write.called)
            self.assertEqual(
                file_mock.write.call_args,
                mock.call(
                    "https://certification.canonical.com/submissions/status/EXAMPLE"
                ),
            )

    def test__export_results_c3_legacy_prints_also_to_file(self):
        """
        That the the c3 legacy exporter also reports back the C3 submission url
        after submitting
        """
        self_mock = mock.MagicMock()
        self_mock.is_interactive = False
        config_mock = self_mock.sa.config
        config_mock.get_value.return_value = "none"

        def get_parametric_sections(section):
            if section == "report":
                return {"c3": {"exporter": "tar", "transport": "c3"}}
            elif section == "exporter":
                return {"tar": {"unit": "some_id"}}
            return {}

        config_mock.get_parametric_sections = get_parametric_sections
        self_mock._export_fn = None
        self_mock.sa.export_to_transport.return_value = {
            "url": "https://certification.canonical.com/submissions/status/EXAMPLE"
        }
        mock_open = mock.mock_open()
        with mock.patch("checkbox_ng.launcher.stages.open", mock_open) as f:
            ReportsStage._export_results(self_mock)
            file_mock = f.return_value
            self.assertTrue(file_mock.write.called)
            self.assertEqual(
                file_mock.write.call_args,
                mock.call(
                    "https://certification.canonical.com/submissions/status/EXAMPLE"
                ),
            )
