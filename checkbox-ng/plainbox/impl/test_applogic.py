# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
plainbox.impl.test_applogic
===========================

Test definitions for plainbox.impl.applogic module
"""

from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.applogic import get_matching_job_list, run_job_if_possible
from plainbox.impl.job import JobDefinition
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.testing_utils import make_job
from plainbox.vendor import mock


class FunctionTests(TestCase):

    def test_get_matching_job_list(self):
        origin = mock.Mock(name="origin", spec_set=Origin)
        job_list = [make_job("foo"), make_job("froz"), make_job("barg")]
        self.assertEqual(
            get_matching_job_list(job_list, RegExpJobQualifier("f.*", origin)),
            [make_job("foo"), make_job("froz")],
        )


class RunJobIfPossibleTests(TestCase):
    """Tests for run_job_if_possible function."""

    def setUp(self):
        self.job = JobDefinition({"id": "test-job", "plugin": "shell"})
        self.job_state = mock.Mock()
        self.session = mock.Mock()
        self.session.job_state_map = {"test-job": self.job_state}
        self.runner = mock.Mock()
        self.config = mock.Mock()

    def test_job_can_start(self):
        """When job can start, runner.run_job is called."""
        self.job_state.can_start.return_value = True
        job_result = MemoryJobResult({"outcome": IJobResult.OUTCOME_PASS})
        self.runner.run_job.return_value = job_result

        state, result = run_job_if_possible(
            self.session, self.runner, self.config, self.job
        )

        self.runner.run_job.assert_called_once_with(
            self.job, self.job_state, self.config, None
        )
        self.assertEqual(result, job_result)
        self.session.update_job_result.assert_called_once_with(self.job, job_result)
        self.assertEqual(state, self.job_state)

    def test_job_cannot_start_no_skip_reason(self):
        """When job cannot start without skip_reason."""
        self.job_state.can_start.return_value = False
        self.job_state.get_readiness_description.return_value = "Not ready"

        with mock.patch(
            "plainbox.impl.applogic.determine_outcome_and_skip_reason"
        ) as mock_determine:
            mock_determine.return_value = (IJobResult.OUTCOME_NOT_SUPPORTED, None)
            state, result = run_job_if_possible(
                self.session, self.runner, self.config, self.job
            )

            self.assertEqual(result.outcome, IJobResult.OUTCOME_NOT_SUPPORTED)
            self.assertIsNone(result.skip_reason)
            self.assertEqual(result.comments, "Not ready")
            self.runner.run_job.assert_not_called()

    def test_job_cannot_start_with_skip_reason(self):
        """When job cannot start with skip_reason."""
        self.job_state.can_start.return_value = False
        self.job_state.get_readiness_description.return_value = "Skipped"
        skip_reason = {
            "related_dependencies": ["dep-job"],
            "related_resources": [],
            "related_manifests": [],
        }

        with mock.patch(
            "plainbox.impl.applogic.determine_outcome_and_skip_reason"
        ) as mock_determine:
            mock_determine.return_value = (
                IJobResult.OUTCOME_SKIPPED_DEPENDENCY,
                skip_reason,
            )
            state, result = run_job_if_possible(
                self.session, self.runner, self.config, self.job
            )

            self.assertEqual(result.outcome, IJobResult.OUTCOME_SKIPPED_DEPENDENCY)
            self.assertEqual(result.skip_reason, skip_reason)
            self.assertEqual(result.comments, "Skipped")
