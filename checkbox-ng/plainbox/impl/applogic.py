# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.secure import config


def get_matching_job_list(job_list, qualifier):
    """
    Get a list of jobs that are designated by the specified qualifier.

    This is intended to be used with :class:`CompositeQualifier`
    but works with any :class:`IJobQualifier` subclass.
    """
    return [job for job in job_list if qualifier.designates(job)]


def get_whitelist_by_name(provider_list, desired_whitelist):
    """
    Get the first whitelist matching desired_whitelist from the loaded
    providers
    """
    for provider in provider_list:
        for whitelist in provider.get_builtin_whitelists():
            if whitelist.name == desired_whitelist:
                return whitelist
    else:
        raise LookupError(
            "None of the providers had a whitelist "
            "named '{}'".format(desired_whitelist))


def run_job_if_possible(session, runner, config, job, update=True):
    """
    Coupling point for session, runner, config and job

    :returns: (job_state, job_result)
    """
    job_state = session.job_state_map[job.name]
    if job_state.can_start():
        job_result = runner.run_job(job, config)
    else:
        # Set the outcome of jobs that cannot start to
        # OUTCOME_NOT_SUPPORTED _except_ if any of the inhibitors point to
        # a job with an OUTCOME_SKIP outcome, if that is the case mirror
        # that outcome. This makes 'skip' stronger than 'not-supported'
        outcome = IJobResult.OUTCOME_NOT_SUPPORTED
        for inhibitor in job_state.readiness_inhibitor_list:
            if inhibitor.cause != inhibitor.FAILED_DEP:
                continue
            related_job_state = session.job_state_map[
                inhibitor.related_job.name]
            if related_job_state.result.outcome == IJobResult.OUTCOME_SKIP:
                outcome = IJobResult.OUTCOME_SKIP
        job_result = MemoryJobResult({
            'outcome': outcome,
            'comments': job_state.get_readiness_description()
        })
    assert job_result is not None
    if update:
        session.update_job_result(job, job_result)
    return job_state, job_result


class PlainBoxConfig(config.Config):
    """
    Configuration for PlainBox itself
    """

    environment = config.Section(
        help_text="Environment variables for scripts and jobs")

    welcome_text = config.Variable(
        section="common",
        help_text="Welcome text to display prior to test selection/execution")

    default_provider = config.Variable(
        section="common",
        help_text="Name of the default provider to use",
        validator_list=[
            config.ChoiceValidator(['auto', 'src', 'deb', 'stub', 'ihv'])],
        default="auto")

    class Meta:

        # TODO: properly depend on xdg and use real code that also handles
        # XDG_CONFIG_HOME.
        filename_list = [
            '/etc/xdg/plainbox.conf',
            os.path.expanduser('~/.config/plainbox.conf')]
