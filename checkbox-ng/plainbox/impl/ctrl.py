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
:mod:`plainbox.impl.ctrl` -- Controller Classes
===============================================

Session controller classes implement the glue between models (jobs, test plans,
session state) and the rest of the application. They encapsulate knowledge that
used to be special-cased and sprinkled around various parts of both plainbox
and particular plainbox-using applications.

Execution controllers are used by the :class:`~plainbox.impl.runner.JobRunner`
class to select the best method to execute a command of a particular job.  This
is mostly applicable to jobs that need to run as another user, typically as
root, as the method that is used to effectively gain root differs depending on
circumstances.
"""

import abc
import contextlib
import errno
try:
    import grp
except ImportError:
    grp = None
import itertools
import json
import logging
import os
import tempfile
import subprocess
import sys
import threading
from subprocess import check_output, CalledProcessError, STDOUT

from plainbox.abc import IJobResult
from plainbox.abc import ISessionStateController
from plainbox.i18n import gettext as _
from plainbox.impl import get_plainbox_dir
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.depmgr import DependencyMissingError
from plainbox.impl.resource import ExpressionCannotEvaluateError
from plainbox.impl.resource import ExpressionFailedError
from plainbox.impl.resource import ResourceProgramError
from plainbox.impl.resource import Resource
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.origin import JobOutputTextSource
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.secure.rfc822 import gen_rfc822_records
from plainbox.impl.session.jobs import InhibitionCause
from plainbox.impl.session.jobs import JobReadinessInhibitor
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.template import TemplateUnit
from plainbox.impl.unit.unit import MissingParam
from plainbox.impl.validation import Severity
from plainbox.vendor import morris
from plainbox.vendor import extcmd

__all__ = [
    'CheckBoxSessionStateController',
    'checkbox_session_state_ctrl',
]


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
            set of pairs (dep_type, job_id)

        Returns a set of pairs (dep_type, job_id) that describe all
        dependencies of the specified job. The first element in the pair,
        dep_type, is either DEP_TYPE_DIRECT, DEP_TYPE_ORDERING or
        DEP_TYPE_RESOURCE. The second element is the id of the job.
        """
        direct = DependencyMissingError.DEP_TYPE_DIRECT
        ordering = DependencyMissingError.DEP_TYPE_ORDERING
        resource = DependencyMissingError.DEP_TYPE_RESOURCE
        direct_deps = job.get_direct_dependencies()
        after_deps = job.get_after_dependencies()
        try:
            resource_deps = job.get_resource_dependencies()
        except ResourceProgramError:
            resource_deps = ()
        result = set(itertools.chain(
            zip(itertools.repeat(direct), direct_deps),
            zip(itertools.repeat(resource), resource_deps),
            zip(itertools.repeat(ordering), after_deps)))
        return result

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
        inhibitors = []
        # Check if all job resource requirements are met
        prog = job.get_resource_program()
        if prog is not None:
            try:
                prog.evaluate_or_raise(session_state.resource_map)
            except ExpressionCannotEvaluateError as exc:
                for resource_id in exc.expression.resource_id_list:
                    if session_state.job_state_map[resource_id].result.outcome == 'pass':
                        continue
                    # Lookup the related job (the job that provides the
                    # resources needed by the expression that cannot be
                    # evaluated)
                    related_job = session_state.job_state_map[resource_id].job
                    # Add A PENDING_RESOURCE inhibitor as we are unable to
                    # determine if the resource requirement is met or not. This
                    # can happen if the resource job did not ran for any reason
                    # (it can either be prevented from running by normal means
                    # or simply be on the run_list but just was not executed
                    # yet).
                    inhibitor = JobReadinessInhibitor(
                        cause=InhibitionCause.PENDING_RESOURCE,
                        related_job=related_job,
                        related_expression=exc.expression)
                    inhibitors.append(inhibitor)
            except ExpressionFailedError as exc:
                # When expressions fail then all the associated resources are
                # marked as failed since we don't want to get into the analysis
                # of logic expressions to know any "better".
                for resource_id in exc.expression.resource_id_list:
                    # Lookup the related job (the job that provides the
                    # resources needed by the expression that failed)
                    related_job = session_state.job_state_map[resource_id].job
                    # Add a FAILED_RESOURCE inhibitor as we have all the data
                    # to run the requirement program but it simply returns a
                    # non-True value. This typically indicates a missing
                    # software package or necessary hardware.
                    inhibitor = JobReadinessInhibitor(
                        cause=InhibitionCause.FAILED_RESOURCE,
                        related_job=related_job,
                        related_expression=exc.expression)
                    inhibitors.append(inhibitor)
        # Check if all job dependencies ran successfully
        for dep_id in sorted(job.get_direct_dependencies()):
            dep_job_state = session_state.job_state_map[dep_id]
            # If the dependency did not have a chance to run yet add the
            # PENDING_DEP inhibitor.
            if dep_job_state.result.outcome == IJobResult.OUTCOME_NONE:
                inhibitor = JobReadinessInhibitor(
                    cause=InhibitionCause.PENDING_DEP,
                    related_job=dep_job_state.job)
                inhibitors.append(inhibitor)
            # If the dependency is anything but successful add the
            # FAILED_DEP inhibitor. In theory the PENDING_DEP code above
            # could be discarded but this would loose context and would
            # prevent the operator from actually understanding why a job
            # cannot run.
            elif dep_job_state.result.outcome != IJobResult.OUTCOME_PASS:
                inhibitor = JobReadinessInhibitor(
                    cause=InhibitionCause.FAILED_DEP,
                    related_job=dep_job_state.job)
                inhibitors.append(inhibitor)
        # Check if all "after" dependencies ran yet
        for dep_id in sorted(job.get_after_dependencies()):
            dep_job_state = session_state.job_state_map[dep_id]
            # If the dependency did not have a chance to run yet add the
            # PENDING_DEP inhibitor.
            if dep_job_state.result.outcome == IJobResult.OUTCOME_NONE:
                inhibitor = JobReadinessInhibitor(
                    cause=InhibitionCause.PENDING_DEP,
                    related_job=dep_job_state.job)
                inhibitors.append(inhibitor)
        for dep_id in sorted(job.get_salvage_dependencies()):
            dep_job_state = session_state.job_state_map[dep_id]
            if dep_job_state.result.outcome != IJobResult.OUTCOME_FAIL:
                inhibitor = JobReadinessInhibitor(
                    cause=InhibitionCause.NOT_FAILED_DEP,
                    related_job=dep_job_state.job)
                inhibitors.append(inhibitor)
        return inhibitors

    def observe_result(self, session_state, job, result,
                       fake_resources=False):
        """
        Notice the specified test result and update readiness state.

        :param session_state:
            A SessionState object
        :param job:
            A JobDefinition object
        :param result:
            A IJobResult object
        :param fake_resources:
            An optional parameter to trigger test plan export execution mode
            using fake resourceobjects

        This function updates the internal result collection with the data from
        the specified test result. Results can safely override older results.
        Results also change the ready map (jobs that can run) because of
        dependency relations.

        Some results have deeper meaning, those are results for resource jobs.
        They are discussed in detail below:

        Resource jobs produce resource records which are used as data to run
        requirement expressions against. Each time a result for a resource job
        is presented to the session it will be parsed as a collection of RFC822
        records. A new entry is created in the resource map (entirely replacing
        any old entries), with a list of the resources that were parsed from
        the IO log.
        """
        # Store the result in job_state_map
        session_state.job_state_map[job.id].result = result
        session_state.on_job_state_map_changed()
        session_state.on_job_result_changed(job, result)
        # Treat some jobs specially and interpret their output
        if job.plugin == "resource":
            self._process_resource_result(
                session_state, job, result, fake_resources)

    def _process_resource_result(self, session_state, job, result,
                                 fake_resources=False):
        """
        Analyze a result of a CheckBox "resource" job and generate
        or replace resource records.
        """
        self._parse_and_store_resource(session_state, job, result)
        if session_state.resource_map[job.id] != [Resource({})]:
            self._instantiate_templates(
                session_state, job, result, fake_resources)

    def _parse_and_store_resource(self, session_state, job, result):
        # NOTE: https://bugs.launchpad.net/checkbox/+bug/1297928
        # If we are resuming from a session that had a resource job that
        # never ran, we will see an empty MemoryJobResult object.
        # Processing empty I/O log would create an empty resource list
        # and that state is different from the state the session started
        # before it was suspended, so don't
        if result.outcome is IJobResult.OUTCOME_NONE:
            return
        new_resource_list = []
        for record in gen_rfc822_records_from_io_log(job, result):
            # XXX: Consider forwarding the origin object here.  I guess we
            # should have from_frc822_record as with JobDefinition
            resource = Resource(record.data)
            logger.debug(
                _("Storing resource record %r: %s"), job.id, resource)
            new_resource_list.append(resource)
        # Create an empty resource object to properly fail __getattr__ calls
        if not new_resource_list:
            new_resource_list = [Resource({})]
        # Replace any old resources with the new resource list
        session_state.set_resource_list(job.id, new_resource_list)

    def _instantiate_templates(self, session_state, job, result,
                               fake_resources=False):
        # NOTE: https://bugs.launchpad.net/checkbox/+bug/1297928
        # If we are resuming from a session that had a resource job that
        # never ran, we will see an empty MemoryJobResult object.
        # Processing empty I/O log would create an empty resource list
        # and that state is different from the state the session started
        # before it was suspended, so don't
        if result.outcome is IJobResult.OUTCOME_NONE:
            return
        for unit in session_state.unit_list:
            if isinstance(unit, TemplateUnit) and unit.resource_id == job.id:
                logger.info(_("Instantiating unit: %s"), unit)
                for new_unit in unit.instantiate_all(
                        session_state.resource_map[job.id], fake_resources):
                    try:
                        check_result = new_unit.check()
                    except MissingParam as m:
                        logger.debug(_("Ignoring %s with missing "
                                         "template parameter %s"),
                                         new_unit._raw_data.get('id'),
                                         m.parameter)
                        continue
                    # Only ignore jobs for which check() returns an error
                    if [c for c in check_result
                            if c.severity == Severity.error]:
                        logger.error(_("Ignoring invalid generated job %s"),
                                     new_unit.id)
                    else:
                        session_state.add_unit(new_unit, via=job, recompute=False)
        session_state._recompute_job_readiness()


def gen_rfc822_records_from_io_log(job, result):
    """
    Convert io_log from a job result to a sequence of rfc822 records
    """
    logger.debug(_("processing output from a job: %r"), job)
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
            # TRANSLATORS: keep the word "local" untranslated. It is a
            # special type of job that needs to be distinguished.
            _("local script %s returned invalid RFC822 data: %s"),
            job.id, exc)


checkbox_session_state_ctrl = CheckBoxSessionStateController()


class SymLinkNest:
    """
    A class for setting up a control directory with symlinked executables
    """

    def __init__(self, dirname):
        self._dirname = dirname

    def add_provider(self, provider):
        """
        Add all of the executables associated a particular provider

        :param provider:
            A Provider1 instance
        """
        for filename in provider.executable_list:
            self.add_executable(filename)

    def add_executable(self, filename):
        """
        Add a executable to the control directory
        """
        logger.debug(
            _("Adding executable %s to nest %s"),
            filename, self._dirname)
        dest = os.path.join(self._dirname, os.path.basename(filename))
        try:
            os.symlink(filename, dest)
        except OSError as exc:
            # Allow symlinks to fail on Windows where it requires some
            # untold voodoo magic to work (aka running as root)
            logger.error(
                _("Unable to create symlink s%s -> %s: %r"),
                filename, dest, exc)
