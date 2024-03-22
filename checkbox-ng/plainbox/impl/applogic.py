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
:mod:`plainbox.impl.applogic` -- application logic
==================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import os

from plainbox.abc import IJobResult
from plainbox.i18n import gettext as _
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.secure import config
from plainbox.impl.secure.qualifiers import select_units
from plainbox.impl.session import SessionManager
from plainbox.impl.session.jobs import InhibitionCause


# Deprecated, use plainbox.impl.secure.qualifiers.select_units() instead
def get_matching_job_list(job_list, qualifier):
    """
    Get a list of jobs that are designated by the specified qualifier.

    This is intended to be used with :class:`CompositeQualifier`
    but works with any :class:`IUnitQualifier` subclass.
    """
    return select_units(job_list, [qualifier])


def run_job_if_possible(session, runner, config, job, update=True, ui=None):
    """
    Coupling point for session, runner, config and job

    :returns: (job_state, job_result)
    """
    job_state = session.job_state_map[job.id]
    if job_state.can_start():
        job_result = runner.run_job(job, job_state, config, ui)
    else:
        # Set the outcome of jobs that cannot start to
        # OUTCOME_NOT_SUPPORTED _except_ if any of the inhibitors point to
        # a job with an OUTCOME_SKIP outcome, if that is the case mirror
        # that outcome. This makes 'skip' stronger than 'not-supported'
        outcome = IJobResult.OUTCOME_NOT_SUPPORTED
        for inhibitor in job_state.readiness_inhibitor_list:
            if inhibitor.cause != InhibitionCause.FAILED_DEP:
                continue
            related_job_state = session.job_state_map[inhibitor.related_job.id]
            if related_job_state.result.outcome == IJobResult.OUTCOME_SKIP:
                outcome = IJobResult.OUTCOME_SKIP
        job_result = MemoryJobResult(
            {
                "outcome": outcome,
                "comments": job_state.get_readiness_description(),
            }
        )
    assert job_result is not None
    if update:
        session.update_job_result(job, job_result)
    return job_state, job_result


def get_all_exporter_names():
    """
    Get the identifiers (names) of all the supported session state exporters.

    :returns:
        A list of session exporter names (identifiers) available from all the
        providers.

    This function creates a temporary session associated with the local
    device and adds all of the available providers to it. Finally, it returns
    the list of exporter names. The session is transparently destroyed.
    """
    with SessionManager.get_throwaway_manager() as manager:
        return list(manager.exporter_map.keys())
