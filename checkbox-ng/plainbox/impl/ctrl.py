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

Session controller classes implement the glue between models (jobs, whitelists,
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
import grp
import itertools
import logging
import os
import posix
import tempfile
from subprocess import check_output, CalledProcessError, STDOUT

from plainbox.abc import IExecutionController
from plainbox.abc import IJobResult
from plainbox.abc import ISessionStateController
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.depmgr import DependencyMissingError
from plainbox.impl.job import JobDefinition
from plainbox.impl.job import JobOutputTextSource
from plainbox.impl.resource import ExpressionCannotEvaluateError
from plainbox.impl.resource import ExpressionFailedError
from plainbox.impl.resource import Resource
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.secure.rfc822 import gen_rfc822_records
from plainbox.impl.session.jobs import JobReadinessInhibitor

__all__ = [
    'CheckBoxSessionStateController',
    'RootViaPTL1ExecutionController',
    'RootViaPkexecExecutionController',
    'RootViaSudoExecutionController',
    'UserJobExecutionController',
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
        for filename in provider.get_all_executables():
            self.add_executable(filename)

    def add_executable(self, filename):
        """
        Add a executable to the control directory
        """
        logger.debug(
            "Adding executable %s to nest %s",
            filename, self._dirname)
        os.symlink(
            filename, os.path.join(
                self._dirname, os.path.basename(filename)))


class CheckBoxExecutionController(IExecutionController):
    """
    Base class for checkbox-like execution controllers.

    This abstract class provides common features for all checkbox execution
    controllers.
    """

    def __init__(self, session_dir, provider_list):
        """
        Initialize a new CheckBoxExecutionController

        :param session_dir:
            Base directory of the session this job will execute in.
            This directory is used to co-locate some data that is unique to
            this execution as well as data that is shared by all executions.
        :param provider_list:
            A list of Provider1 objects that will be available for script
            dependency resolutions. Currently all of the scripts are makedirs
            available but this will be refined to the minimal set later.
        """
        self._session_dir = session_dir
        self._provider_list = provider_list

    def execute_job(self, job, config, extcmd_popen):
        """
        Execute the specified job using the specified subprocess-like object

        :param job:
            The JobDefinition to execute
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. It is used to
            provide values for missing environment variables that are required
            by the job (as expressed by the environ key in the job definition
            file).
        :param extcmd_popen:
            A subprocess.Popen like object
        :returns:
            The return code of the command, as returned by subprocess.call()
        """
        # CHECKBOX_DATA is where jobs can share output.
        # It has to be an directory that scripts can assume exists.
        if not os.path.isdir(self.CHECKBOX_DATA):
            os.makedirs(self.CHECKBOX_DATA)
        # Setup the executable nest directory
        with self.configured_filesystem(job, config) as nest_dir:
            # Get the command and the environment.
            # of this execution controller
            cmd = self.get_execution_command(job, config, nest_dir)
            env = self.get_execution_environment(job, config, nest_dir)
            # run the command
            logger.debug("job[%s] executing %r with env %r",
                         job.name, cmd, env)
            return extcmd_popen.call(cmd, env=env)

    @contextlib.contextmanager
    def configured_filesystem(self, job, config):
        """
        Context manager for handling filesystem aspects of job execution.

        :param job:
            The JobDefinition to execute
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. It is used to
            provide values for missing environment variables that are required
            by the job (as expressed by the environ key in the job definition
            file).
        :returns:
            Pathname of the executable symlink nest directory.
        """
        # Create a nest for all the private executables needed for execution
        prefix = 'nest-'
        suffix = '.{}'.format(job.checksum)
        with tempfile.TemporaryDirectory(suffix, prefix) as nest_dir:
            logger.debug("Symlink nest for executables: %s", nest_dir)
            nest = SymLinkNest(nest_dir)
            # Add all providers executables to PATH
            for provider in self._provider_list:
                nest.add_provider(provider)
            logger.debug("Symlink nest for executables: %s", nest_dir)
            yield nest_dir

    def get_score(self, job):
        """
        Compute how applicable this controller is for the specified job.

        :returns:
            A numeric score, or None if the controller cannot run this job.
            The higher the value, the more applicable this controller is.
        """
        if isinstance(job, JobDefinition):
            return self.get_checkbox_score(job)
        else:
            return -1

    @abc.abstractmethod
    def get_checkbox_score(self, job):
        """
        Compute how applicable this controller is for the specified job.

        The twist is that it is always a checkbox job definition so we can be
        more precise.

        :returns:
            A number that specifies how applicable this controller is for the
            specified job (the higher the better) or None if it cannot be used
            at all
        """

    @abc.abstractmethod
    def get_execution_command(self, job, config, nest_dir):
        """
        Get the command to execute the specified job

        :param job:
            job definition with the command and environment definitions
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. It is used to
            provide values for missing environment variables that are required
            by the job (as expressed by the environ key in the job definition
            file).
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. This argument may or may not be used,
            depending on how PATH is passed to the command (via environment or
            via the commant line)
        :returns:
            List of command arguments
        """

    def get_execution_environment(self, job, config, nest_dir):
        """
        Get the environment required to execute the specified job:

        :param job:
            job definition with the command and environment definitions
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. It is used to
            provide values for missing environment variables that are required
            by the job (as expressed by the environ key in the job definition
            file).
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. This argument may or may not be used,
            depending on how PATH is passed to the command (via environment or
            via the commant line)
        :return:
            dictionary with the environment to use.

        This returned environment has additional PATH, PYTHONPATH entries. It
        also uses fixed LANG so that scripts behave as expected.  Lastly it
        sets CHECKBOX_SHARE and CHECKBOX_DATA that may be required by some
        scripts.
        """
        # Get a proper environment
        env = dict(os.environ)
        # Use non-internationalized environment
        env['LANG'] = 'C.UTF-8'
        if 'LANGUAGE' in env:
            del env['LANGUAGE']
        for name in list(env.keys()):
            if name.startswith("LC_"):
                del env[name]
        # Use PATH that can lookup checkbox scripts
        if job.provider.extra_PYTHONPATH:
            env['PYTHONPATH'] = os.pathsep.join(
                [job.provider.extra_PYTHONPATH]
                + env.get("PYTHONPATH", "").split(os.pathsep))
        # Inject nest_dir into PATH
        env['PATH'] = os.pathsep.join(
            [nest_dir]
            + env.get("PATH", "").split(os.pathsep))
        # Add CHECKBOX_SHARE that is needed by one script
        env['CHECKBOX_SHARE'] = job.provider.CHECKBOX_SHARE
        # Add CHECKBOX_DATA (temporary checkbox data)
        env['CHECKBOX_DATA'] = self.CHECKBOX_DATA
        # Inject additional variables that are requested in the config
        if config is not None and config.environment is not Unset:
            for env_var in config.environment:
                # Don't override anything that is already present in the
                # current environment. This will allow users to customize
                # variables without editing any config files.
                if env_var in env:
                    continue
                # If the environment section of the configuration file has a
                # particular variable then copy it over.
                env[env_var] = config.environment[env_var]
        return env

    @property
    def CHECKBOX_DATA(self):
        """
        value of the CHECKBOX_DATA environment variable.

        This variable names a sub-directory of the session directory
        where jobs can share data between invocations.
        """
        return os.path.join(self._session_dir, "CHECKBOX_DATA")


class UserJobExecutionController(CheckBoxExecutionController):
    """
    An execution controller that works for jobs invoked as the current user.
    """

    def get_execution_command(self, job, config, nest_dir):
        """
        Get the command to execute the specified job

        :param job:
            job definition with the command and environment definitions
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. Ignored.
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. Ingored.
        :returns:
            List of command arguments

        This basically returns ['bash', '-c', job.command]
        """
        return ['bash', '-c', job.command]

    def get_checkbox_score(self, job):
        """
        Compute how applicable this controller is for the specified job.

        :returns:
            1 for jobs without a user override, 3 for jobs with user override
            if the invoking uid is 0 (root), -1 otherwise
        """
        if job.user is None:
            return 1
        if os.getuid() == 0:
            return 4
        else:
            return -1


class CheckBoxDifferentialExecutionController(CheckBoxExecutionController):
    """
    A CheckBoxExecutionController subclass that uses differential environment.

    This special subclass has a special :meth:`get_execution_environment()`
    method that always returns None. Instead the new method
    :meth:`get_differential_execution_environment()` that returns the
    difference between the target environment and the current environment.
    """

    def get_differential_execution_environment(self, job, config, nest_dir):
        """
        Get the environment required to execute the specified job:

        :param job:
            job definition with the command and environment definitions
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. It is used to
            provide values for missing environment variables that are required
            by the job (as expressed by the environ key in the job definition
            file).
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. This is simply passed to
            :meth:`get_execution_environment()` directly.
        :returns:
            Differential environment (see below).

        This implementation computes the desired environment (as it was
        computed in the base class) and then discards all of the environment
        variables that are identical in both sets. The exception are variables
        that are mentioned in
        :meth:`plainbox.impl.job.JobDefinition.get_environ_settings()` which
        are always retained.
        """
        base_env = os.environ
        target_env = super().get_execution_environment(job, config, nest_dir)
        return {
            key: value
            for key, value in target_env.items()
            if key not in base_env or base_env[key] != value
            or key in job.get_environ_settings()
        }

    def get_execution_environment(self, job, config, nest_dir):
        """
        Get the environment required to execute the specified job:

        :param job:
            job definition with the command and environment definitions.
            Ignored.
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. Ignored.
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. Ignored.
        :returns:
            None

        This implementation always returns None since the environment is always
        passed in via :meth:`get_execution_command()`
        """
        return None


class RootViaPTL1ExecutionController(CheckBoxDifferentialExecutionController):
    """
    Execution controller that gains root using plainbox-trusted-launcher-1
    """

    def __init__(self, session_dir, provider_list):
        """
        Initialize a new RootViaPTL1ExecutionController
        """
        super().__init__(session_dir, provider_list)
        # Ask pkaction(1) if the "run-plainbox-job" policykit action is
        # registered on this machine.
        action_id = b"org.freedesktop.policykit.pkexec.run-plainbox-job"
        # Catch CalledProcessError because pkaction (polkit < 0.110) always
        # exits with status 1, see:
        # https://bugs.freedesktop.org/show_bug.cgi?id=29936#attach_78263
        try:
            result = check_output(["pkaction", "--action-id", action_id],
                                  stderr=STDOUT)
        except CalledProcessError as exc:
            result = exc.output
        self.is_supported = True if result.strip() == action_id else False

    def get_execution_command(self, job, config, nest_dir):
        """
        Get the command to invoke.

        :param job:
            job definition with the command and environment definitions
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. Passed to
            :meth:`get_differential_execution_environment()`.
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. Passed to
            :meth:`get_differential_execution_environment()`.

        This overridden implementation returns especially crafted command that
        uses pkexec to run the plainbox-trusted-launcher-1 as the desired user
        (typically root). It passes the checksum of the job definition as
        argument, along with all of the required environment key-value pairs.
        If a job is generated it also passes the special via attribute to let
        the trusted launcher discover the generated job. Currently it supports
        at most one-level of generated jobs.
        """
        # Run plainbox-trusted-launcher-1 as the required user
        cmd = ['pkexec', '--user', job.user, 'plainbox-trusted-launcher-1']
        # Pass a special switch when working from source
        if job.provider.name == '2013.com.canonical:checkbox-src':
            cmd += ['--development']
        # Run the specified generator job in the specified environment
        if job.via is not None:
            cmd += ['--generator', job.via]
            parent_env = self.get_differential_execution_environment(
                job.origin.source.job, config, nest_dir)
            for key, value in sorted(parent_env.items()):
                cmd += ['-G', '{}={}'.format(key, value)]
        # Run the specified target job in the specified environment
        cmd += ['--target', job.checksum]
        env = self.get_differential_execution_environment(
            job, config, nest_dir)
        for key, value in sorted(env.items()):
            cmd += ['-T', '{}={}'.format(key, value)]
        return cmd

    def get_checkbox_score(self, job):
        """
        Compute how applicable this controller is for the specified job.

        :returns:
            two for jobs with an user override that can be invoked by the
            trusted launcher, zero for jobs without an user override that can
            be invoked by the trusted launcher, -1 otherwise
        """
        # Only works with jobs coming from the Provider1 instance
        if not isinstance(job.provider, Provider1):
            return -1
        # Be very appropriate for running jobs in the source provider
        if (os.getenv('PLAINBOX_USE_TRUSTED_LAUNCHER')
                and job.user is not None
                and job.provider.name == '2013.com.canonical:checkbox-src'):
            return 100
        # Only works with jobs loaded from the secure PROVIDERPATH
        if not job.provider.secure:
            return -1
        # Only makes sense with jobs that need to run as another user
        # Promote this controller only if the trusted launcher is authorized to
        # run jobs as another user
        if job.user is not None and self.is_supported:
            return 3
        else:
            return 0


class RootViaPkexecExecutionController(
        CheckBoxDifferentialExecutionController):
    """
    Execution controller that gains root by using pkexec.

    This controller should be used for jobs that need root but cannot be
    executed by the plainbox-trusted-launcher-1. This happens whenever the job
    is not in the system-wide provider location.

    In practice it is used when working with the special
    'checkbox-in-source-tree' provider as well as for jobs that need to run as
    root from the non-system-wide location.
    """

    def get_execution_command(self, job, config, nest_dir):
        """
        Get the command to invoke.

        :param job:
            job definition with the command and environment definitions
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. Passed to
            :meth:`get_differential_execution_environment()`.
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. Passed to
            :meth:`get_differential_execution_environment()`.

        Since we cannot pass environment in the ordinary way while using
        pkexec(1) (pkexec starts new processes in a sanitized, pristine,
        environment) we're relying on env(1) to pass some of the environment
        variables that we require.
        """
        # Run env(1) as the required user
        cmd = ['pkexec', '--user', job.user, 'env']
        # Append all environment data
        env = self.get_differential_execution_environment(
            job, config, nest_dir)
        cmd += ["{key}={value}".format(key=key, value=value)
                for key, value in sorted(env.items())]
        # Lastly use bash -c, to run our command
        cmd += ['bash', '-c', job.command]
        return cmd

    def get_checkbox_score(self, job):
        """
        Compute how applicable this controller is for the specified job.

        :returns:
            one for jobs with a user override, zero otherwise
        """
        if job.user is not None:
            return 1
        else:
            return 0


class RootViaSudoExecutionController(
        CheckBoxDifferentialExecutionController):
    """
    Execution controller that gains root by using sudo.

    This controller should be used for jobs that need root but cannot be
    executed by the plainbox-trusted-launcher-1.

    This happens whenever the job is not in the system-wide provider location.
    In practice it is used when working with the special
    'checkbox-in-source-tree' provider as well as for jobs that need to run as
    root from the non-system-wide location.

    Using this controller is preferable to pkexec if running on command line as
    unlike pkexec, it retains 'memory' and doesn't ask for the password over
    and over again.
    """

    def __init__(self, session_dir, provider_list):
        """
        Initialize a new RootViaSudoExecutionController

        :param session_dir:
            Base directory of the session this job will execute in.
            This directory is used to co-locate some data that is unique to
            this execution as well as data that is shared by all executions.
        """
        super().__init__(session_dir, provider_list)
        # Check if the user can use 'sudo' on this machine. This check is a bit
        # Ubuntu specific and can be wrong due to local configuration but
        # without a better API all we can do is guess.
        #
        # Shamelessly stolen from command-not-found
        try:
            in_sudo_group = grp.getgrnam("sudo").gr_gid in posix.getgroups()
        except KeyError:
            in_sudo_group = False
        try:
            in_admin_group = grp.getgrnam("admin").gr_gid in posix.getgroups()
        except KeyError:
            in_admin_group = False
        self.user_can_sudo = in_sudo_group or in_admin_group

    def get_execution_command(self, job, config, nest_dir):
        """
        Get the command to invoke.

        :param job:
            job definition with the command and environment definitions
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. Ignored.
        :param nest_dir:
            A directory with a nest of symlinks to all executables required to
            execute the specified job. Ingored.

        Since we cannot pass environment in the ordinary way while using
        sudo(8) (even passing -E doesn't get us everything due to security
        features built into sudo itself) we're relying on env(1) to pass some
        of the environment variables that we require.
        """
        # Run env(1) as the required user
        cmd = ['sudo', '-u', job.user, 'env']
        # Append all environment data
        env = self.get_differential_execution_environment(
            job, config, nest_dir)
        cmd += ["{key}={value}".format(key=key, value=value)
                for key, value in sorted(env.items())]
        # Lastly use bash -c, to run our command
        cmd += ['bash', '-c', job.command]
        return cmd

    def get_checkbox_score(self, job):
        """
        Compute how applicable this controller is for the specified job.

        :returns:
            -1 if the job does not have a user override or the user cannot use
            sudo and 2 otherwise
        """
        # Only makes sense with jobs that need to run as another user
        if job.user is not None and self.user_can_sudo:
            return 2
        else:
            return -1
