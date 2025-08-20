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
from functools import partial
from unittest import TestCase, mock

from checkbox_ng.launcher.stages import MainLoopStage, ReportsStage, IJobResult


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

    def test__run_jobs(self):
        self_mock = mock.MagicMock()
        job_done_mock = mock.MagicMock(id="done_job", estimated_duration=100)
        job_todo_mock = mock.MagicMock(id="todo_job", estimated_duration=200)
        job_done_state_mock = mock.MagicMock(result_history=["some_result"])
        job_todo_state_mock = mock.MagicMock(result_history=[])
        self_mock.sa.get_job.side_effect = [job_done_mock, job_todo_mock]
        self_mock.sa.get_job_state.side_effect = [
            job_done_state_mock,
            job_todo_state_mock,
        ]
        run_single_job_mock = mock.MagicMock()
        self_mock._run_single_job_with_ui_loop = run_single_job_mock
        result_builder_mock = mock.MagicMock()
        result_builder_mock.get_result.return_value = "job_result"
        run_single_job_mock.return_value = result_builder_mock
        jobs_to_run = ["done_job", "todo_job"]

        MainLoopStage._run_jobs(self_mock, jobs_to_run)

        self.assertEqual(self_mock.sa.get_job.call_count, 2)
        self.assertEqual(self_mock.sa.get_job_state.call_count, 2)
        self.assertEqual(self_mock._run_single_job_with_ui_loop.call_count, 1)

    def test__run_setup_jobs(self):
        self_mock = mock.MagicMock()

        job_ids = ["job_success", "job_fail", "job_crash"]
        job_success_state_mock = mock.MagicMock()
        job_success_state_mock.result.outcome = IJobResult.OUTCOME_PASS

        job_fail_state_mock = mock.MagicMock()
        job_fail_state_mock.result.outcome = IJobResult.OUTCOME_FAIL

        job_crash_state_mock = mock.MagicMock()
        job_crash_state_mock.result.outcome = IJobResult.OUTCOME_CRASH

        self_mock.sa.get_job_state.side_effect = [
            job_success_state_mock,
            job_fail_state_mock,
            job_crash_state_mock,
        ]

        failed_jobs = MainLoopStage._run_setup_jobs(self_mock, job_ids)

        self_mock._run_jobs.assert_called_once_with(job_ids)
        self.assertEqual(self_mock.sa.get_job_state.call_count, len(job_ids))
        expected_failed_jobs = [
            ("job_fail", IJobResult.OUTCOME_FAIL),
            ("job_crash", IJobResult.OUTCOME_CRASH),
        ]
        self.assertCountEqual(failed_jobs, expected_failed_jobs)


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
                    "https://certification.canonical.com/submissions/status/EXAMPLE\n"
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
                    "https://certification.canonical.com/submissions/status/EXAMPLE\n"
                ),
            )

    @mock.patch("os.makedirs")
    def test__prepare_stock_report_submission_files(self, makedirs):
        self_mock = mock.MagicMock()
        self_mock._get_submission_file_path = partial(
            ReportsStage._get_submission_file_path, self_mock
        )
        self_mock.base_dir = "~/.local/share"

        ReportsStage._prepare_stock_report(self_mock, "submission_files")

        self.assertEqual(self_mock.sa.config.update_from_another.call_count, 3)
        self.assertTrue(makedirs.called)

    @mock.patch("os.makedirs")
    def test__prepare_stock_report_submission_json(self, makedirs):
        self_mock = mock.MagicMock()
        self_mock.sa.configuration_type.side_effect = AttributeError
        self_mock._get_submission_file_path = partial(
            ReportsStage._get_submission_file_path, self_mock
        )
        self_mock.base_dir = "~/.local/share"

        ReportsStage._prepare_stock_report(self_mock, "submission_json")

        # called to adopt the generated config
        self_mock_update_from_another = self_mock.sa.config.update_from_another
        self.assertEqual(self_mock_update_from_another.call_count, 1)
        config = self_mock_update_from_another.call_args[0][0]
        self.assertFalse(config.get_problems())
        self.assertTrue(makedirs.called)
