# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
:mod:`plainbox.impl.runner` -- job runner
=========================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import collections
import datetime
import json
import logging
import os
import string

from plainbox.vendor import extcmd

from plainbox.abc import IJobRunner
from plainbox.impl.result import JobResult, IOLogRecord, IoLogEncoder

logger = logging.getLogger("plainbox.runner")


def slugify(_string):
    """
    Slugify - like Django does for URL - transform a random string to a valid
    slug that can be later used in filenames
    """
    valid_chars = frozenset(
        "-_.{}{}".format(string.ascii_letters, string.digits))
    return ''.join(c if c in valid_chars else '_' for c in _string)


def io_log_write(log, stream):
    """
    JSON call to serialize io_log objects to disk
    """
    json.dump(
        log, stream, ensure_ascii=False, indent=None, cls=IoLogEncoder,
        separators=(',', ':'))


class CommandIOLogBuilder(extcmd.DelegateBase):
    """
    Delegate for extcmd that builds io_log entries.

    IO log entries are records kept by JobResult.io_log and correspond to all
    of the data that was written by called process. The format is a sequence of
    tuples (delay, stream_name, data).
    """

    def on_begin(self, args, kwargs):
        """
        Internal method of extcmd.DelegateBase

        Called when a command is being invoked.
        Begins tracking time (relative time entries) and creates the empty
        io_log list.
        """
        logger.debug("io log starting for command: %r", args)
        self.io_log = []
        self.last_msg = datetime.datetime.utcnow()

    def on_line(self, stream_name, line):
        """
        Internal method of IOLogBuilder

        Appends each line to the io_log. Maintains a timestamp of the last
        message so that approximate delay between each piece of output can be
        recorded as well.
        """
        now = datetime.datetime.utcnow()
        delay = now - self.last_msg
        self.last_msg = now
        record = IOLogRecord(delay.total_seconds(), stream_name, line)
        self.io_log.append(record)
        logger.debug("io log captured %r", record)


class CommandOutputWriter(extcmd.DelegateBase):
    """
    Delegate for extcmd that writes output to a file on disk.

    The file itself is only opened once on_begin() gets called by extcmd. This
    makes it safe to instantiate this without worrying about dangling
    resources.
    """

    def __init__(self, stdout_path, stderr_path):
        """
        Initialize new writer.

        Just records output paths.
        """
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path

    def on_begin(self, args, kwargs):
        """
        Internal method of extcmd.DelegateBase

        Called when a command is being invoked
        """
        self.stdout = open(self.stdout_path, "wb")
        self.stderr = open(self.stderr_path, "wb")

    def on_end(self, returncode):
        """
        Internal method of extcmd.DelegateBase

        Called when a command finishes running
        """
        self.stdout.close()
        self.stderr.close()

    def on_line(self, stream_name, line):
        """
        Internal method of extcmd.DelegateBase

        Called for each line of output.
        """
        if stream_name == 'stdout':
            self.stdout.write(line)
        elif stream_name == 'stderr':
            self.stderr.write(line)


class FallbackCommandOutputPrinter(extcmd.DelegateBase):
    """
    Delegate for extcmd that prints all output to stdout.

    This delegate is only used as a fallback when no delegate was explicitly
    provided to a JobRunner instance.
    """

    def __init__(self, prompt):
        self._prompt = prompt
        self._lineno = collections.defaultdict(int)
        self._abort = False

    def on_line(self, stream_name, line):
        if self._abort:
            return
        self._lineno[stream_name] += 1
        try:
            print("(job {}, <{}:{:05}>) {}".format(
                self._prompt, stream_name, self._lineno[stream_name],
                line.decode('UTF-8').rstrip()))
        except UnicodeDecodeError:
            self._abort = True


class JobRunner(IJobRunner):
    """
    Runner for jobs - executes jobs and produces results

    The runner is somewhat de-coupled from jobs and session. It still carries
    all checkbox-specific logic about the various types of plugins.

    The runner consumes jobs and configuration objects and produces job result
    objects. The runner can operate in dry-run mode, when enabled, most jobs
    are never started. Only jobs listed in DRY_RUN_PLUGINS are executed.
    """

    # List of plugins that are still executed
    _DRY_RUN_PLUGINS = ('local', 'resource', 'attachment')

    def __init__(self, session_dir, jobs_io_log_dir,
                 command_io_delegate=None, outcome_callback=None,
                 dry_run=False):
        """
        Initialize a new job runner.

        Uses the specified session_dir as CHECKBOX_DATA environment variable.
        Uses the specified IO delegate for extcmd.ExternalCommandWithDelegate
        to track IO done by the called commands (optional, a simple console
        printer is provided if missing).
        """
        self._session_dir = session_dir
        self._jobs_io_log_dir = jobs_io_log_dir
        self._command_io_delegate = command_io_delegate
        self._outcome_callback = outcome_callback
        self._dry_run = dry_run

    def run_job(self, job, config=None):
        """
        Run the specified job an return the result
        """
        logger.info("Running %r", job)
        func_name = "_plugin_" + job.plugin.replace('-', '_')
        try:
            runner = getattr(self, func_name)
        except AttributeError:
            return JobResult({
                'job': job,
                'outcome': JobResult.OUTCOME_NOT_IMPLEMENTED,
                'comment': 'This plugin is not supported'
            })
        else:
            if self._dry_run and job.plugin not in self._DRY_RUN_PLUGINS:
                return self._dry_run_result(job)
            else:
                return runner(job, config)

    def _dry_run_result(self, job):
        """
        Produce the result that is used when running in dry-run mode
        """
        return JobResult({
            'job': job,
            'outcome': JobResult.OUTCOME_SKIP,
            'comments': "Job skipped in dry-run mode"
        })

    def _plugin_shell(self, job, config):
        return self._just_run_command(job, config)

    _plugin_attachment = _plugin_shell

    def _plugin_resource(self, job, config):
        return self._just_run_command(job, config)

    def _plugin_local(self, job, config):
        return self._just_run_command(job, config)

    def _plugin_manual(self, job, config):
        if self._outcome_callback is None:
            return JobResult({
                'job': job,
                'outcome': JobResult.OUTCOME_SKIP,
                'comment': "non-interactive test run"
            })
        else:
            result = self._just_run_command(job, config)
            # XXX: make outcome writable
            result._data['outcome'] = self._outcome_callback()
            return result

    _plugin_user_interact = _plugin_manual
    _plugin_user_verify = _plugin_manual

    def _just_run_command(self, job, config):
        # Run the embedded command
        return_code, io_log = self._run_command(job, config)
        # Convert the return of the command to the outcome of the job
        if return_code == 0:
            outcome = JobResult.OUTCOME_PASS
        else:
            outcome = JobResult.OUTCOME_FAIL
        # Create a result object and return it
        return JobResult({
            'job': job,
            'outcome': outcome,
            'return_code': return_code,
            'io_log': io_log
        })

    def _get_script_env(self, job, config=None, only_changes=False):
        """
        Compute the environment the script will be executed in
        """
        # Get a proper environment
        env = dict(os.environ)
        # Use non-internationalized environment
        env['LANG'] = 'C.UTF-8'
        # Allow the job to customize anything
        job.modify_execution_environment(env, self._session_dir, config)
        # If a differential environment is requested return only the subset
        # that has been altered.
        #
        # XXX: This will effectively give the root user our PATH which _may_ be
        # good bud _might_ be dangerous. This will need some peer review.
        if only_changes:
            return {key: value
                    for key, value in env.items()
                    if key not in os.environ or os.environ[key] != value
                    or key in job.get_environ_settings()}
        else:
            return env

    def _run_command(self, job, config):
        """
        Run the shell command associated with the specified job.

        Returns a tuple (return_code, io_log)
        """
        # Bail early if there is nothing do do
        if job.command is None:
            return None, ()
        ui_io_delegate = self._command_io_delegate
        # If there is no UI delegate specified create a simple
        # delegate that logs all output to the console
        if ui_io_delegate is None:
            ui_io_delegate = FallbackCommandOutputPrinter(job.name)
        # Create a delegate that writes all IO to disk
        slug = slugify(job.name)
        output_writer = CommandOutputWriter(
            stdout_path=os.path.join(self._jobs_io_log_dir,
                                     "{}.stdout".format(slug)),
            stderr_path=os.path.join(self._jobs_io_log_dir,
                                     "{}.stderr".format(slug)))
        # Create a delegate that builds a log of all IO
        io_log_builder = CommandIOLogBuilder()
        # Create the delegate for routing IO
        #
        #
        # Split the stream of data into three parts (each part is expressed as
        # an element of extcmd.Chain()).
        #
        # Send the first copy of the data through bytes->text decoder and
        # then to the UI delegate. This cold be something provided by the
        # higher level caller or the default CommandOutputLogger.
        #
        # Send the second copy of the data to the _IOLogBuilder() instance that
        # just concatenates subsequent bytes into neat time-stamped records.
        #
        # Send the third copy to the output writer that writes everything to
        # disk.
        delegate = extcmd.Chain([
            ui_io_delegate,
            io_log_builder,
            output_writer])
        logger.debug("job[%s] extcmd delegate: %r", job.name, delegate)
        # Create a subprocess.Popen() like object that uses the delegate
        # system to observe all IO as it occurs in real time.
        logging_popen = extcmd.ExternalCommandWithDelegate(delegate)
        # Start the process and wait for it to finish getting the
        # result code. This will actually call a number of callbacks
        # while the process is running. It will also spawn a few
        # threads although all callbacks will be fired from a single
        # thread (which is _not_ the main thread)
        logger.debug("job[%s] starting command: %s", job.name, job.command)
        # XXX: sadly using /bin/sh results in broken output
        # XXX: maybe run it both ways and raise exceptions on differences?
        cmd = ['bash', '-c', job.command]
        if job.user is not None:
            # When the job requires to run as root then elevate our permissions
            # via pkexec(1). Since pkexec resets environment we need to somehow
            # pass the extra things we require. To do that we use the env(1)
            # command and pass it the list of changed environment variables.
            #
            # The whole pkexec and env part gets prepended to the command we
            # were supposed to run.
            cmd = ['pkexec', '--user', job.user, 'env'] + [
                "{key}={value}".format(key=key, value=value)
                for key, value in self._get_script_env(
                    job, config, only_changes=True
                ).items()
            ] + cmd
            logging.debug("job[%s] executing %r", job.name, cmd)
            return_code = logging_popen.call(cmd)
        else:
            logging.debug("job[%s] executing %r", job.name, cmd)
            return_code = logging_popen.call(
                cmd, env=self._get_script_env(job, config))
        logger.debug("job[%s] command return code: %r",
                     job.name, return_code)
        # XXX: Perhaps handle process dying from signals here
        # When the process is killed proc.returncode is not set
        # and another (cannot remember now) attribute is set
        fjson = os.path.join(self._jobs_io_log_dir, "{}.json".format(slug))
        with open(fjson, "wt") as stream:
            io_log_write(io_log_builder.io_log, stream)
            stream.flush()
            os.fsync(stream.fileno())
        return return_code, fjson
