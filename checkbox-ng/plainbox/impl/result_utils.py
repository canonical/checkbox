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

"""
Utilities for handling job results and skip reasons.

:mod:`plainbox.impl.result_utils` -- result utilities
=====================================================

This module provides utilities for working with job results, particularly
for determining skip outcomes and extracting skip reason information from
job readiness inhibitors.
"""

from plainbox.abc import IJobResult
from plainbox.impl.session.jobs import InhibitionCause


def determine_outcome_and_skip_reason(job_state, job_state_map):
    """
    Determine the correct outcome and skip_reason for a job that cannot start.

    This function examines the job's readiness inhibitors and determines:
    1. The most appropriate outcome (SKIPPED_DEPENDENCY, SKIPPED_RESOURCE, or
       SKIPPED_MANIFEST), with special handling for manual skip outcomes
    2. A skip_reason dict containing structured information about why the job
       cannot start

    Outcome determination follows this priority:
    - If any dependency was manually skipped, outcome is OUTCOME_SKIP
    - Else if there are failed manifest expressions, outcome is OUTCOME_SKIPPED_MANIFEST
    - Else if there are FAILED_DEP inhibitors, outcome is OUTCOME_SKIPPED_DEPENDENCY
    - Else if there are failed resource expressions, outcome is OUTCOME_SKIPPED_RESOURCE
    - Else outcome is OUTCOME_NOT_SUPPORTED

    :param job_state:
        A JobState object containing readiness_inhibitor_list and result info
    :param job_state_map:
        A mapping of job ids to JobState objects (from session)
    :returns:
        A tuple of (outcome: str, skip_reason: dict or None)
        where skip_reason is a dict with optional keys:
        - related_dependencies: list of job ids that failed
        - related_resources: list of resource expressions that failed
        - related_manifests: list of manifest expressions that failed
    """
    if not job_state.readiness_inhibitor_list:
        return IJobResult.OUTCOME_NOT_SUPPORTED, None

    # Check for manual skip outcome and collect all inhibitors
    outcome = None
    skip_reason = {
        "related_dependencies": [],
        "related_resources": [],
        "related_manifests": [],
    }

    # Track what we've seen to build skip_reason
    has_failed_dep = False
    has_failed_resource = False
    has_failed_manifest = False

    for inhibitor in job_state.readiness_inhibitor_list:
        if inhibitor.cause == InhibitionCause.FAILED_DEP:
            has_failed_dep = True
            # Check if the dependency was manually skipped
            if inhibitor.related_job:
                related_job_state = job_state_map.get(inhibitor.related_job.id)
                if (
                    related_job_state
                    and related_job_state.result
                    and related_job_state.result.outcome
                    == IJobResult.OUTCOME_SKIP
                ):
                    outcome = IJobResult.OUTCOME_SKIP
                else:
                    skip_reason["related_dependencies"].append(
                        inhibitor.related_job.id
                    )
        elif inhibitor.cause == InhibitionCause.FAILED_RESOURCE:
            has_failed_resource = True
            if inhibitor.related_expression:
                # Check if this is a manifest expression
                if inhibitor.related_expression.manifest_id_list:
                    has_failed_manifest = True
                    skip_reason["related_manifests"].append(
                        inhibitor.related_expression.text
                    )
                else:
                    skip_reason["related_resources"].append(
                        inhibitor.related_expression.text
                    )

    # If we found a manual skip, use that outcome
    if outcome == IJobResult.OUTCOME_SKIP:
        return outcome, (
            skip_reason if skip_reason["related_dependencies"] else None
        )

    # Determine outcome based on priority:
    # FAILED_MANIFEST > FAILED_DEP > FAILED_RESOURCE
    if has_failed_manifest:
        outcome = IJobResult.OUTCOME_SKIPPED_MANIFEST
    elif has_failed_dep:
        outcome = IJobResult.OUTCOME_SKIPPED_DEPENDENCY
    elif has_failed_resource:
        outcome = IJobResult.OUTCOME_SKIPPED_RESOURCE
    else:
        outcome = IJobResult.OUTCOME_NOT_SUPPORTED

    # Return skip_reason only if we have any inhibitors to report
    if (
        skip_reason["related_dependencies"]
        or skip_reason["related_resources"]
        or skip_reason["related_manifests"]
    ):
        return outcome, skip_reason
    else:
        return outcome, None
