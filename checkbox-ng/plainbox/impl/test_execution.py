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

from plainbox.impl.execution import UnifiedRunner
from plainbox.impl.unit.job import InvalidJob

from unittest import TestCase, mock


class UnifiedRunnerTests(TestCase):
    def test_run_job_invalid_job(self):
        self_mock = mock.MagicMock()

        invalid_unit = mock.MagicMock(
            _data={"id": "generated_id_{param}"}, parameters={}
        )
        invalid_job = InvalidJob.from_unit(invalid_unit, errors=["Some error"])
        ui = mock.MagicMock()

        result = UnifiedRunner.run_job(self_mock, invalid_job, None, ui=ui)

        output_writer = self_mock._job_runner_ui_delegate
        self.assertTrue(output_writer.on_begin.called)
        # error is reported via the ui
        self.assertTrue(output_writer.on_chunk.called)
        self.assertTrue(output_writer.on_end.called)
        self.assertEqual(result.outcome, "fail")
