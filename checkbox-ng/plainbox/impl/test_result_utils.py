# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

import unittest
from unittest.mock import Mock

from plainbox.abc import IJobResult
from plainbox.impl.result_utils import determine_outcome_and_skip_reason
from plainbox.impl.session.jobs import InhibitionCause


class DetermineOutcomeAndSkipReasonTests(unittest.TestCase):
    """Tests for the determine_outcome_and_skip_reason function."""

    def test_no_inhibitors(self):
        """Test with no readiness inhibitors."""
        job_state = Mock()
        job_state.readiness_inhibitor_list = []

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, {}
        )

        self.assertEqual(outcome, IJobResult.OUTCOME_NOT_SUPPORTED)
        self.assertIsNone(skip_reason)

    def test_single_failed_dep_inhibitor(self):
        """Test with a single FAILED_DEP inhibitor."""
        related_job = Mock()
        related_job.id = "job1"

        inhibitor = Mock()
        inhibitor.cause = InhibitionCause.FAILED_DEP
        inhibitor.related_job = related_job

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor]

        job_state_map = {"job1": Mock(result=Mock(outcome="fail"))}

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, job_state_map
        )

        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_DEPENDENCY)
        self.assertIsNotNone(skip_reason)
        self.assertIn("job1", skip_reason["related_dependencies"])
        self.assertEqual(skip_reason["related_resources"], [])
        self.assertEqual(skip_reason["related_manifests"], [])

    def test_multiple_failed_deps(self):
        """Test with multiple FAILED_DEP inhibitors."""
        job1 = Mock()
        job1.id = "job1"
        job2 = Mock()
        job2.id = "job2"

        inhibitor1 = Mock()
        inhibitor1.cause = InhibitionCause.FAILED_DEP
        inhibitor1.related_job = job1

        inhibitor2 = Mock()
        inhibitor2.cause = InhibitionCause.FAILED_DEP
        inhibitor2.related_job = job2

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor1, inhibitor2]

        job_state_map = {
            "job1": Mock(result=Mock(outcome="fail")),
            "job2": Mock(result=Mock(outcome="fail")),
        }

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, job_state_map
        )

        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_DEPENDENCY)
        self.assertIn("job1", skip_reason["related_dependencies"])
        self.assertIn("job2", skip_reason["related_dependencies"])

    def test_failed_resource_inhibitor(self):
        """Test with a FAILED_RESOURCE inhibitor."""
        expr = Mock()
        expr.text = "cpuinfo.count > 2"
        expr.manifest_id_list = []

        inhibitor = Mock()
        inhibitor.cause = InhibitionCause.FAILED_RESOURCE
        inhibitor.related_expression = expr

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor]

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, {}
        )

        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_RESOURCE)
        self.assertIsNotNone(skip_reason)
        self.assertIn("cpuinfo.count > 2", skip_reason["related_resources"])
        self.assertEqual(skip_reason["related_dependencies"], [])
        self.assertEqual(skip_reason["related_manifests"], [])

    def test_failed_manifest_inhibitor(self):
        """Test with a FAILED_RESOURCE inhibitor for a manifest."""
        expr = Mock()
        expr.text = "manifest.has_thunderbolt3 == 'True'"
        expr.manifest_id_list = ["com.canonical.plainbox::manifest-id"]

        inhibitor = Mock()
        inhibitor.cause = InhibitionCause.FAILED_RESOURCE
        inhibitor.related_expression = expr

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor]

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, {}
        )

        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_MANIFEST)
        self.assertIsNotNone(skip_reason)
        self.assertIn(
            "manifest.has_thunderbolt3 == 'True'",
            skip_reason["related_manifests"],
        )
        self.assertEqual(skip_reason["related_dependencies"], [])
        self.assertEqual(skip_reason["related_resources"], [])

    def test_multiple_failed_resources(self):
        """Test with multiple FAILED_RESOURCE inhibitors."""
        expr1 = Mock()
        expr1.text = "package.name == 'pkg1'"
        expr1.manifest_id_list = []

        expr2 = Mock()
        expr2.text = "package.name == 'pkg2'"
        expr2.manifest_id_list = []

        inhibitor1 = Mock()
        inhibitor1.cause = InhibitionCause.FAILED_RESOURCE
        inhibitor1.related_expression = expr1

        inhibitor2 = Mock()
        inhibitor2.cause = InhibitionCause.FAILED_RESOURCE
        inhibitor2.related_expression = expr2

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor1, inhibitor2]

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, {}
        )

        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_RESOURCE)
        self.assertIn("package.name == 'pkg1'", skip_reason["related_resources"])
        self.assertIn("package.name == 'pkg2'", skip_reason["related_resources"])

    def test_mixed_inhibitors_dep_priority(self):
        """Test that FAILED_DEP takes priority over FAILED_RESOURCE."""
        dep_job = Mock()
        dep_job.id = "job1"

        dep_inhibitor = Mock()
        dep_inhibitor.cause = InhibitionCause.FAILED_DEP
        dep_inhibitor.related_job = dep_job

        expr = Mock()
        expr.text = "cpuinfo.count > 2"
        expr.manifest_id_list = []

        res_inhibitor = Mock()
        res_inhibitor.cause = InhibitionCause.FAILED_RESOURCE
        res_inhibitor.related_expression = expr

        job_state = Mock()
        job_state.readiness_inhibitor_list = [res_inhibitor, dep_inhibitor]

        job_state_map = {"job1": Mock(result=Mock(outcome="fail"))}

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, job_state_map
        )

        # FAILED_DEP should take priority
        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_DEPENDENCY)
        # But skip_reason should include both
        self.assertIn("job1", skip_reason["related_dependencies"])
        self.assertIn("cpuinfo.count > 2", skip_reason["related_resources"])

    def test_mixed_inhibitors_manifest_priority(self):
        """Test that FAILED_MANIFEST takes priority over FAILED_RESOURCE."""
        manifest_expr = Mock()
        manifest_expr.text = "manifest.has_feature == 'True'"
        manifest_expr.manifest_id_list = ["com.canonical.plainbox::manifest-id"]

        manifest_inhibitor = Mock()
        manifest_inhibitor.cause = InhibitionCause.FAILED_RESOURCE
        manifest_inhibitor.related_expression = manifest_expr

        resource_expr = Mock()
        resource_expr.text = "cpuinfo.count > 2"
        resource_expr.manifest_id_list = []

        resource_inhibitor = Mock()
        resource_inhibitor.cause = InhibitionCause.FAILED_RESOURCE
        resource_inhibitor.related_expression = resource_expr

        job_state = Mock()
        job_state.readiness_inhibitor_list = [
            resource_inhibitor,
            manifest_inhibitor,
        ]

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, {}
        )

        # FAILED_MANIFEST should take priority over other FAILED_RESOURCE
        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_MANIFEST)
        # But skip_reason should include both
        self.assertIn(
            "manifest.has_feature == 'True'", skip_reason["related_manifests"]
        )
        self.assertIn("cpuinfo.count > 2", skip_reason["related_resources"])

    def test_manual_skip_of_dependency(self):
        """Test that manual skip of a dependency results in OUTCOME_SKIP."""
        related_job = Mock()
        related_job.id = "job1"

        inhibitor = Mock()
        inhibitor.cause = InhibitionCause.FAILED_DEP
        inhibitor.related_job = related_job

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor]

        # The related job was manually skipped
        skipped_result = Mock()
        skipped_result.outcome = IJobResult.OUTCOME_SKIP

        job_state_map = {"job1": Mock(result=skipped_result)}

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, job_state_map
        )

        self.assertEqual(outcome, IJobResult.OUTCOME_SKIP)
        # skip_reason should not include the dependency since it was manually skipped
        self.assertIsNone(skip_reason)

    def test_undesired_inhibitor_ignored(self):
        """Test that UNDESIRED inhibitor is ignored."""
        inhibitor = Mock()
        inhibitor.cause = InhibitionCause.UNDESIRED
        inhibitor.related_job = None

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor]

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, {}
        )

        # UNDESIRED should not affect the outcome
        self.assertEqual(outcome, IJobResult.OUTCOME_NOT_SUPPORTED)
        self.assertIsNone(skip_reason)

    def test_pending_resource_inhibitor_ignored(self):
        """Test that PENDING_RESOURCE inhibitor is ignored."""
        expr = Mock()
        expr.text = "cpuinfo.count > 2"

        inhibitor = Mock()
        inhibitor.cause = InhibitionCause.PENDING_RESOURCE
        inhibitor.related_expression = expr

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor]

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, {}
        )

        # PENDING_RESOURCE should not affect the outcome
        self.assertEqual(outcome, IJobResult.OUTCOME_NOT_SUPPORTED)
        self.assertIsNone(skip_reason)

    def test_skip_reason_structure(self):
        """Test that skip_reason has the correct structure."""
        related_job = Mock()
        related_job.id = "job1"

        inhibitor = Mock()
        inhibitor.cause = InhibitionCause.FAILED_DEP
        inhibitor.related_job = related_job

        job_state = Mock()
        job_state.readiness_inhibitor_list = [inhibitor]

        job_state_map = {"job1": Mock(result=Mock(outcome="fail"))}

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, job_state_map
        )

        # Check structure
        self.assertIsInstance(skip_reason, dict)
        self.assertIn("related_dependencies", skip_reason)
        self.assertIn("related_resources", skip_reason)
        self.assertIn("related_manifests", skip_reason)
        self.assertIsInstance(skip_reason["related_dependencies"], list)
        self.assertIsInstance(skip_reason["related_resources"], list)
        self.assertIsInstance(skip_reason["related_manifests"], list)

    def test_complex_scenario(self):
        """Test a complex scenario with multiple inhibitors of different types."""
        # Create inhibitors
        job1 = Mock()
        job1.id = "job1"
        job2 = Mock()
        job2.id = "job2"

        dep_inhibitor1 = Mock()
        dep_inhibitor1.cause = InhibitionCause.FAILED_DEP
        dep_inhibitor1.related_job = job1

        dep_inhibitor2 = Mock()
        dep_inhibitor2.cause = InhibitionCause.FAILED_DEP
        dep_inhibitor2.related_job = job2

        resource_expr = Mock()
        resource_expr.text = "cpuinfo.count > 4"
        resource_expr.manifest_id_list = []

        resource_inhibitor = Mock()
        resource_inhibitor.cause = InhibitionCause.FAILED_RESOURCE
        resource_inhibitor.related_expression = resource_expr

        manifest_expr = Mock()
        manifest_expr.text = "manifest.has_touchpad == 'True'"
        manifest_expr.manifest_id_list = ["has_touchpad"]

        manifest_inhibitor = Mock()
        manifest_inhibitor.cause = InhibitionCause.FAILED_RESOURCE
        manifest_inhibitor.related_expression = manifest_expr

        job_state = Mock()
        job_state.readiness_inhibitor_list = [
            dep_inhibitor1,
            resource_inhibitor,
            dep_inhibitor2,
            manifest_inhibitor,
        ]

        job_state_map = {
            "job1": Mock(result=Mock(outcome="fail")),
            "job2": Mock(result=Mock(outcome="fail")),
        }

        outcome, skip_reason = determine_outcome_and_skip_reason(
            job_state, job_state_map
        )

        # FAILED_MANIFEST should take priority
        self.assertEqual(outcome, IJobResult.OUTCOME_SKIPPED_MANIFEST)
        # But skip_reason should include all inhibitors
        self.assertIn("job1", skip_reason["related_dependencies"])
        self.assertIn("job2", skip_reason["related_dependencies"])
        self.assertIn("cpuinfo.count > 4", skip_reason["related_resources"])
        self.assertIn(
            "manifest.has_touchpad == 'True'", skip_reason["related_manifests"]
        )
