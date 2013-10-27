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
:mod:`plainbox.impl.ctrl` -- Controller Classes
===============================================

Controller classes implement the glue between models (jobs, whitelists, session
state) and the rest of the application. They encapsulate knowledge that used to
be special-cased and sprinkled around various parts of both plainbox and
particular plainbox-using applications.
"""

import itertools
import logging

from plainbox.abc import IJobResult
from plainbox.abc import ISessionStateController
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.depmgr import DependencyMissingError
from plainbox.impl.job import JobOutputTextSource
from plainbox.impl.resource import ExpressionCannotEvaluateError
from plainbox.impl.resource import ExpressionFailedError
from plainbox.impl.resource import Resource
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.secure.rfc822 import gen_rfc822_records
from plainbox.impl.session.jobs import JobReadinessInhibitor

__all__ = ['checkbox_session_state_ctrl', 'CheckBoxSessionStateController']


logger = logging.getLogger("plainbox.ctrl")


class CheckBoxSessionStateController(ISessionStateController):
    """
    A combo controller for CheckBox-like jobs.

    This controller implements the following features:

        * A job may depend on another job, this is expressed via the 'depends'
          attribute. Cyclic dependencies are not allowed. A job will become
          inhibited if any of its dependencies have outcome other than
          OUTCOME_PASS
        * A job may require that a particular resource expression evaluates to
          true. This is expressed via the 'requires' attribute. A job will
          become inhibited if any of the requirement programs evaluates to
          value other than True.
        * A job may have the attribute 'plugin' equal to "local" which will
          cause the controller to interpret the stdout of the command as a set
          of job definitions.
        * A job may have the attribute 'plugin' equal to "resource" which will
          cause the controller to interpret the stdout of the command as a set
          of resource definitions.
    """

    def get_dependency_set(self, job):
        """
        Get the set of direct dependencies of a particular job.

        :param job:
            A IJobDefinition instance that is to be visited
        :returns:
            set of pairs (dep_type, job_name)

        Returns a set of pairs (dep_type, job_name) that describe all
        dependencies of the specified job. The first element in the pair,
        dep_type, is either DEP_TYPE_DIRECT or DEP_TYPE_RESOURCE. The second
        element is the name of the job.
        """
        direct = DependencyMissingError.DEP_TYPE_DIRECT
        resource = DependencyMissingError.DEP_TYPE_RESOURCE
        return set(itertools.chain(
            zip(itertools.repeat(direct), job.get_direct_dependencies()),
            zip(itertools.repeat(resource), job.get_resource_dependencies())))

    def get_inhibitor_list(self, session_state, job):
        """
        Get a list of readiness inhibitors that inhibit a particular job.

        :param session_state:
            A SessionState instance that is used to interrogate the
            state of the session where it matters for a particular
            job. Currently this is used to access resources and job
            results.
        :param job:
            A JobDefinition instance
        :returns:
            List of JobReadinessInhibitor
        """
        # Check if all job resource requirements are met
        prog = job.get_resource_program()
        inhibitors = []
        if prog is not None:
            try:
                prog.evaluate_or_raise(session_state.resource_map)
            except ExpressionCannotEvaluateError as exc:
                # Lookup the related job (the job that provides the
                # resources needed by the expression that cannot be
                # evaluated)
                related_job = session_state.job_state_map[
                    exc.expression.resource_name].job
                # Add A PENDING_RESOURCE inhibitor as we are unable to
                # determine if the resource requirement is met or not. This
                # can happen if the resource job did not ran for any reason
                # (it can either be prevented from running by normal means
                # or simply be on the run_list but just was not executed
                # yet).
                inhibitor = JobReadinessInhibitor(
                    cause=JobReadinessInhibitor.PENDING_RESOURCE,
                    related_job=related_job,
                    related_expression=exc.expression)
                inhibitors.append(inhibitor)
            except ExpressionFailedError as exc:
                # Lookup the related job (the job that provides the
                # resources needed by the expression that failed)
                related_job = session_state.job_state_map[
                    exc.expression.resource_name].job
                # Add a FAILED_RESOURCE inhibitor as we have all the data
                # to run the requirement program but it simply returns a
                # non-True value. This typically indicates a missing
                # software package or necessary hardware.
                inhibitor = JobReadinessInhibitor(
                    cause=JobReadinessInhibitor.FAILED_RESOURCE,
                    related_job=related_job,
                    related_expression=exc.expression)
                inhibitors.append(inhibitor)
        # Check if all job dependencies ran successfully
        for dep_name in sorted(job.get_direct_dependencies()):
            dep_job_state = session_state.job_state_map[dep_name]
            # If the dependency did not have a chance to run yet add the
            # PENDING_DEP inhibitor.
            if dep_job_state.result.outcome == IJobResult.OUTCOME_NONE:
                inhibitor = JobReadinessInhibitor(
                    cause=JobReadinessInhibitor.PENDING_DEP,
                    related_job=dep_job_state.job)
                inhibitors.append(inhibitor)
            # If the dependency is anything but successful add the
            # FAILED_DEP inhibitor. In theory the PENDING_DEP code above
            # could be discarded but this would loose context and would
            # prevent the operator from actually understanding why a job
            # cannot run.
            elif dep_job_state.result.outcome != IJobResult.OUTCOME_PASS:
                inhibitor = JobReadinessInhibitor(
                    cause=JobReadinessInhibitor.FAILED_DEP,
                    related_job=dep_job_state.job)
                inhibitors.append(inhibitor)
        return inhibitors

    def observe_result(self, session_state, job, result):
        """
        Notice the specified test result and update readiness state.

        :param session_state:
            A SessionState object
        :param job:
            A JobDefinition object
        :param result:
            A IJobResult object

        This function updates the internal result collection with the data from
        the specified test result. Results can safely override older results.
        Results also change the ready map (jobs that can run) because of
        dependency relations.

        Some results have deeper meaning, those are results for local and
        resource jobs. They are discussed in detail below:

        Resource jobs produce resource records which are used as data to run
        requirement expressions against. Each time a result for a resource job
        is presented to the session it will be parsed as a collection of RFC822
        records. A new entry is created in the resource map (entirely replacing
        any old entries), with a list of the resources that were parsed from
        the IO log.

        Local jobs produce more jobs. Like with resource jobs, their IO log is
        parsed and interpreted as additional jobs. Unlike in resource jobs
        local jobs don't replace anything. They cannot replace an existing job
        with the same name.
        """
        # Store the result in job_state_map
        session_state.job_state_map[job.name].result = result
        session_state.on_job_state_map_changed()
        session_state.on_job_result_changed(job, result)
        # Treat some jobs specially and interpret their output
        if job.plugin == "resource":
            self._process_resource_result(session_state, job, result)
        elif job.plugin == "local":
            self._process_local_result(session_state, job, result)

    def _process_resource_result(self, session_state, job, result):
        """
        Analyze a result of a CheckBox "resource" job and generate
        or replace resource records.
        """
        new_resource_list = []
        for record in gen_rfc822_records_from_io_log(job, result):
            # XXX: Consider forwarding the origin object here.  I guess we
            # should have from_frc822_record as with JobDefinition
            resource = Resource(record.data)
            logger.info("Storing resource record %r: %s", job.name, resource)
            new_resource_list.append(resource)
        # Replace any old resources with the new resource list
        session_state.set_resource_list(job.name, new_resource_list)

    def _process_local_result(self, session_state, job, result):
        """
        Analyze a result of a CheckBox "local" job and generate
        additional job definitions
        """
        # First parse all records and create a list of new jobs (confusing
        # name, not a new list of jobs)
        new_job_list = []
        for record in gen_rfc822_records_from_io_log(job, result):
            new_job = job.create_child_job_from_record(record)
            new_job_list.append(new_job)
        # Then for each new job, add it to the job_list, unless it collides
        # with another job with the same name.
        for new_job in new_job_list:
            try:
                added_job = session_state.add_job(new_job, recompute=False)
            except DependencyDuplicateError as exc:
                # XXX: there should be a channel where such errors could be
                # reported back to the UI layer. Perhaps update_job_result()
                # could simply return a list of problems in a similar manner
                # how update_desired_job_list() does.
                logger.warning(
                    ("Local job %s produced job %r that collides with"
                     " an existing job %s (from %s), the new job was"
                     " discarded"),
                    job, exc.duplicate_job, exc.job, exc.job.origin)
            else:
                # Patch the origin of the existing job so that it traces
                # back to the job that "generated" it again. This is
                # basically required to get __category__ jobs to associate
                # themselves with their children.
                if added_job is not new_job:
                    added_job.update_origin(new_job.origin)


def gen_rfc822_records_from_io_log(job, result):
    """
    Convert io_log from a job result to a sequence of rfc822 records
    """
    logger.debug("processing output from a job: %r", job)
    # Select all stdout lines from the io log
    line_gen = (record[2].decode('UTF-8', errors='replace')
                for record in result.get_io_log()
                if record[1] == 'stdout')
    # Allow the generated records to be traced back to the job that defined
    # the command which produced (printed) them.
    source = JobOutputTextSource(job)
    try:
        # Parse rfc822 records from the subsequent lines
        for record in gen_rfc822_records(line_gen, source=source):
            yield record
    except RFC822SyntaxError as exc:
        # When this exception happens we will _still_ store all the
        # preceding records. This is worth testing
        logger.warning(
            "local script %s returned invalid RFC822 data: %s",
            job, exc)


checkbox_session_state_ctrl = CheckBoxSessionStateController()
