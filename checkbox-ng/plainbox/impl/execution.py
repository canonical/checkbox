# encoding: utf-8
# This file is part of Checkbox.
#
# Copyright 2019 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
Definition for UnifiedRunner class.
"""

import contextlib
import getpass
import gzip
import io
import logging
import os
import select
import subprocess
import sys
import tempfile
import threading
import time

from plainbox.abc import IJobResult, IJobRunner
from plainbox.i18n import gettext as _
from plainbox.impl.result import IOLogRecordWriter
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.runner import CommandOutputWriter
from plainbox.impl.runner import IOLogRecordGenerator
from plainbox.impl.runner import JobRunnerUIDelegate
from plainbox.impl.runner import slugify
from plainbox.impl.jobcache import ResourceJobCache
from plainbox.impl.secure.config import Unset
from plainbox.vendor import extcmd

logger = logging.getLogger("plainbox.unified")


class UnifiedRunner(IJobRunner):
    """
    Class for handling running of jobs.

    Instance of this class should is responsible for creating proper
    environment for job's command can run in.
    """
    def __init__(self, session_dir, provider_list, jobs_io_log_dir,
                 command_io_delegate=None, dry_run=False,
                 execution_ctrl_list=None, stdin=False,
                 normal_user_provider=None, password_provider=None):
        self._session_dir = session_dir
        self._provider_list = provider_list
        if execution_ctrl_list is not None:
            logger.info("Using custom execution controllers is deprecated")
        self._jobs_io_log_dir = jobs_io_log_dir
        self._job_runner_ui_delegate = JobRunnerUIDelegate()
        self._command_io_delegate = command_io_delegate
        self._dry_run = dry_run
        self._resource_cache = ResourceJobCache()
        self._resource_cache.load()
        self._user_provider = normal_user_provider
        self._password_provider = password_provider
        self._stdin = stdin

    def run_job(self, job, job_state, config=None, ui=None):
        logger.info(_("Running %r"), job)

        # resource and attachment jobs are always run (even in dry runs)
        if self._dry_run and job.plugin not in ('resource', 'attachment'):
            return JobResultBuilder(
                outcome=IJobResult.OUTCOME_SKIP,
                comments=_("Job skipped in dry-run mode")
            ).get_result()
        self._job_runner_ui_delegate.ui = ui

        if job.plugin == 'qml':
            return self.run_qml_job(job, job_state, config)

        # for cached resource jobs we get the result using cache
        # if it's not in the cache, ordinary "_run_command" will be run
        if job.plugin == 'resource' and 'cachable' in job.get_flag_set():
            return self._resource_cache.get(
                job.checksum, lambda: self._run_command(
                    job, job_state, config).get_result())

        # manual jobs don't require running anything so we just return
        # the 'undecided' outcome
        if job.plugin == 'manual':
            return JobResultBuilder(
                outcome=IJobResult.OUTCOME_UNDECIDED).get_result()

        # all other kinds of jobs at this point need to run their command
        result_builder = self._run_command(job, config)

        # for user-interact-verify and user-verify jobs the operator chooses
        # the final outcome, so we need to reset the outcome to undecided
        # (from what command's return code would have set)
        if job.plugin in ('user-interact-verify', 'user-verify'):
            result_builder.outcome = IJobResult.OUTCOME_UNDECIDED

        # by this point the result_builder should have all the info needed
        # to yield appropriate result
        return result_builder.get_result()

    def get_warm_up_sequence(self, job_list):
        # we no longer need a warm-up sequence
        # this is left here to conform to the interface
        return []

    def _run_command(self, job, config):
        start_time = time.time()
        slug = slugify(job.id)
        output_writer = CommandOutputWriter(
            stdout_path=os.path.join(
                self._jobs_io_log_dir, "{}.stdout".format(slug)),
            stderr_path=os.path.join(
                self._jobs_io_log_dir, "{}.stderr".format(slug)))
        io_log_gen = IOLogRecordGenerator()
        log = os.path.join(self._jobs_io_log_dir, "{}.record.gz".format(slug))
        with gzip.open(log, mode='wb') as gzip_stream, io.TextIOWrapper(
                gzip_stream, encoding='UTF-8') as record_stream:
            writer = IOLogRecordWriter(record_stream)
            io_log_gen.on_new_record.connect(writer.write_record)
            delegate = extcmd.Chain([
                self._job_runner_ui_delegate, io_log_gen,
                self._command_io_delegate, output_writer])
            ecmd = extcmd.ExternalCommandWithDelegate(delegate)
            return_code = self.execute_job(job, config, ecmd, self._stdin)
            io_log_gen.on_new_record.disconnect(writer.write_record)
        if return_code == 0:
            outcome = IJobResult.OUTCOME_PASS
        elif return_code < 0:
            outcome = IJobResult.OUTCOME_CRASH
        else:
            outcome = IJobResult.OUTCOME_FAIL
        return JobResultBuilder(
            outcome=outcome,
            return_code=return_code,
            io_log_filename=log,
            execution_duration=time.time() - start_time)

    def execute_job(self, job, config, extcmd_popen, stdin=None):
        """Run the 'binary' associated with the job."""
        target_user = job.user or self._user_provider()
        if target_user == getpass.getuser():
            target_user = None

        def call(extcmd_popen, *args, **kwargs):
            """Handle low-level subprocess stuff."""
            is_alive = True
            # Notify that the process is about to start
            extcmd_popen._delegate.on_begin(args, kwargs)
            # Setup stdout/stderr redirection
            kwargs['stdout'] = subprocess.PIPE
            kwargs['stderr'] = subprocess.PIPE
            # Prepare stdio supply
            in_r, in_w = os.pipe()
            # first let's punch the password in
            # we need it only if the target user differs from the one that
            # started checkbox and when changing the user (sudo) requires
            # password
            if target_user and self._password_provider:
                os.write(in_w, self._password_provider() + b'\n')

            def stdin_forwarder(stdin):
                """Forward data from one pipe to the other."""
                # use systems stdin if the stdin pipe wasn't provided
                stdin = stdin or sys.stdin
                try:
                    while is_alive:
                        if stdin in select.select([stdin], [], [], 0)[0]:
                            buf = stdin.readline()
                            if buf == '':
                                os.close(in_w)
                                break
                            os.write(in_w, buf.encode(stdin.encoding))
                        else:
                            time.sleep(0.1)
                except BrokenPipeError:
                    pass
            forwarder_thread = threading.Thread(
                target=stdin_forwarder, args=(stdin,))
            forwarder_thread.start()
            kwargs['stdin'] = in_r

            # Start the process
            proc = extcmd_popen._popen(*args, **kwargs)
            # Setup all worker threads. By now the pipes have been created and
            # proc.stdout/proc.stderr point to open pipe objects.
            stdout_reader = threading.Thread(
                target=extcmd_popen._read_stream, args=(proc.stdout, "stdout"))
            stderr_reader = threading.Thread(
                target=extcmd_popen._read_stream, args=(proc.stderr, "stderr"))
            queue_worker = threading.Thread(target=extcmd_popen._drain_queue)
            # Start all workers
            queue_worker.start()
            stdout_reader.start()
            stderr_reader.start()
            try:
                while True:
                    try:
                        proc.wait()
                        break
                    except KeyboardInterrupt:
                        # On interrupt send a signal to the process
                        extcmd_popen._on_keyboard_interrupt(proc)
                        # And send a notification about this
                        extcmd_popen._delegate.on_interrupt()
            finally:
                # Wait until all worker threads shut down
                stdout_reader.join()
                proc.stdout.close()
                stderr_reader.join()
                proc.stderr.close()
                # Tell the queue worker to shut down
                extcmd_popen._queue.put(None)
                queue_worker.join()
                os.close(in_r)
                is_alive = False
                forwarder_thread.join()
            # Notify that the process has finished
            extcmd_popen._delegate.on_end(proc.returncode)
            return proc.returncode
        if not os.path.isdir(os.path.join(self._session_dir, "CHECKBOX_DATA")):
            os.makedirs(os.path.join(self._session_dir, "CHECKBOX_DATA"))
        # Setup the executable nest directory
        with self.configured_filesystem(job) as nest_dir:
            # Get the command and the environment.
            # of this execution controller
            cmd = get_execution_command(
                job, config, self._session_dir, nest_dir, target_user)
            env = get_execution_environment(
                job, config, self._session_dir, nest_dir)
            # run the command
            logger.debug(_("job[%(ID)s] executing %(CMD)r with env %(ENV)r"
                           " in cwd %(DIR)r"),
                         {"ID": job.id, "CMD": cmd,
                          "ENV": env})
            if 'preserve-cwd' in job.get_flag_set() or os.getenv("SNAP"):
                return_code = call(extcmd_popen, cmd, stdin=subprocess.PIPE,
                        env=env)
            else:
                with self.temporary_cwd(job, config) as cwd_dir:
                    return_code = call(extcmd_popen, cmd,
                            stdin=subprocess.PIPE, env=env, cwd=cwd_dir)
            if 'noreturn' in job.get_flag_set():
                import signal
                signal.pause()
            return return_code

    @contextlib.contextmanager
    def configured_filesystem(self, job):
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
            os.chmod(nest_dir, 0o777)
            logger.debug(_("Symlink nest for executables: %s"), nest_dir)
            from plainbox.impl.ctrl import SymLinkNest
            nest = SymLinkNest(nest_dir)
            # Add all providers sharing namespace with the current job to PATH
            for provider in self._provider_list:
                if job.provider.namespace == provider.namespace:
                    nest.add_provider(provider)
            yield nest_dir

    @contextlib.contextmanager
    def temporary_cwd(self, job, config):
        """
        Context manager for handling temporary current working directory
        for a particular execution of a job definition command.

        :param job:
            The JobDefinition to execute
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. It is used to
            provide values for missing environment variables that are required
            by the job (as expressed by the environ key in the job definition
            file).
        :returns:
            Pathname of the new temporary directory
        """
        # Create a nest for all the private executables needed for execution
        prefix = 'cwd-'
        suffix = '.{}'.format(job.checksum)
        try:
            with tempfile.TemporaryDirectory(suffix, prefix) as cwd_dir:
                logger.debug(
                    _("Job temporary current working directory: %s"), cwd_dir)
                try:
                    yield cwd_dir
                finally:
                    if 'has-leftovers' not in job.get_flag_set():
                        self._check_leftovers(cwd_dir, job)

        except PermissionError as exc:
            logger.warning(
                _("There was a problem with temporary cwd %s, %s"),
                cwd_dir, exc)

    def _check_leftovers(self, cwd_dir, job):
        leftovers = []
        for dirpath, dirnames, filenames in os.walk(cwd_dir):
            if dirpath != cwd_dir:
                leftovers.append(dirpath)
            leftovers.extend(
                os.path.join(dirpath, filename)
                for filename in filenames)
        if leftovers:
            logger.warning(
                _("Job {0} created leftover filesystem artefacts"
                " in its working directory").format(job.id))
            for item in leftovers:
                logger.warning(_("Leftover file/directory: %r"),
                            os.path.relpath(item, cwd_dir))
            logger.warning(
                _("Please store desired files in $PLAINBOX_SESSION_SHARE"
                    "and use regular temporary files for everything else"))

    def get_record_path_for_job(self, job):
        return os.path.join(self._jobs_io_log_dir,
                            "{}.record.gz".format(slugify(job.id)))


class FakeJobRunner(UnifiedRunner):
    """
    Fake runner for jobs.

    Special runner that creates fake resource objects.
    """
    def run_job(self, job, job_state, config=None, ui=None):
        """
        Only one resouce object is created from this runner.
        Exception: 'graphics_card' resource job creates two objects to
        simulate hybrid graphics.
        """
        if job.plugin != 'resource':
            return super().run_job(job, job_state, config, ui)
        builder = JobResultBuilder()
        if job.partial_id == 'graphics_card':
            builder.io_log = [(0, 'stdout', b'a: b\n'),
                              (1, 'stdout', b'\n'),
                              (2, 'stdout', b'a: c\n')]
        else:
            builder.io_log = [(0, 'stdout', b'a: b\n')]
        builder.outcome = 'pass'
        builder.return_code = 0
        return builder.get_result()

def get_execution_environment(job, config, session_dir, nest_dir):
    """
    Get the environment required to execute the specified job:

    :param job:
        job definition with the command and environment definitions
    :param job_state:
        The JobState associated to the job to execute.
    :param config:
        A PlainBoxConfig instance which can be used to load missing environment
        definitions that apply to all jobs. It is used to provide values for
        missing environment variables that are required by the job (as
        expressed by the environ key in the job definition file).
    :param session_dir:
        Base directory of the session this job will execute in.  This directory
        is used to co-locate some data that is unique to this execution as well
        as data that is shared by all executions.
    :param nest_dir:
        A directory with a nest of symlinks to all executables required to
        execute the specified job. This argument may or may not be used,
        depending on how PATH is passed to the command (via environment or via
        the commant line)
    :return:
        dictionary with the environment to use.
    """
    # Get a proper environment
    env = dict(os.environ)
    if 'reset-locale' in job.get_flag_set():
        # Use non-internationalized environment
        env['LANG'] = 'C.UTF-8'
        if 'LANGUAGE' in env:
            del env['LANGUAGE']
        for name in list(env.keys()):
            if name.startswith("LC_"):
                del env[name]
    else:
        # Set the per-provider gettext domain and locale directory
        if job.provider.gettext_domain is not None:
            env['TEXTDOMAIN'] = env['PLAINBOX_PROVIDER_GETTEXT_DOMAIN'] = \
                job.provider.gettext_domain
        if job.provider.locale_dir is not None:
            env['TEXTDOMAINDIR'] = env['PLAINBOX_PROVIDER_LOCALE_DIR'] = \
                job.provider.locale_dir
        if (os.getenv("SNAP") or os.getenv("SNAP_APP_PATH")):
            copy_vars = ['PYTHONHOME', 'PYTHONUSERBASE', 'LD_LIBRARY_PATH',
                         'GI_TYPELIB_PATH']
            for key, value in env.items():
                if key in copy_vars or key.startswith('SNAP'):
                    env[key] = value
    # Use PATH that can lookup checkbox scripts
    if job.provider.extra_PYTHONPATH:
        env['PYTHONPATH'] = os.pathsep.join(
            [job.provider.extra_PYTHONPATH] + env.get(
                "PYTHONPATH", "").split(os.pathsep))
    # Inject nest_dir into PATH
    env['PATH'] = os.pathsep.join(
        [nest_dir] + env.get("PATH", "").split(os.pathsep))
    # Add per-session shared state directory
    env['PLAINBOX_SESSION_SHARE'] = os.path.join(session_dir, "CHECKBOX_DATA")
    def set_if_not_none(envvar, source):
        """Update env if the source variable is not None"""
        if source is not None:
            env[envvar] = source
    set_if_not_none('PLAINBOX_PROVIDER_DATA', job.provider.data_dir)
    set_if_not_none('PLAINBOX_PROVIDER_UNITS', job.provider.units_dir)
    set_if_not_none('CHECKBOX_SHARE', job.provider.CHECKBOX_SHARE)
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

def get_execution_command(job, config, session_dir,
                          nest_dir, target_user=None):
    """Generate a command argv to run in the shell."""
    cmd = []
    if target_user:
        # we want sudo to:
        #   - have no prompt (--prompt '')
        #   - reset the timestamp, so it predictably asks for password
        #     (--reset-timestamp)
        #   - gets password as the first line of stdin (--stdin)
        #   - change the user to the target user (--user)
        cmd = ['sudo', '--prompt', '', '--reset-timestamp', '--stdin',
                '--user', target_user]
    cmd += ['env']
    env = get_execution_environment(job, config, session_dir, nest_dir)
    cmd += ["{key}={value}".format(key=key, value=value)
            for key, value in sorted(env.items())]
    cmd += [job.shell, '-c', job.command]
    return cmd
