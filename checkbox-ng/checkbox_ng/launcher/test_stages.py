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


from unittest import TestCase, mock

from checkbox_ng.launcher.stages import MainLoopStage


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
