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
plainbox.impl.runner
====================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

import collections
import datetime
import logging
import os

from plainbox.vendor import extcmd

from plainbox.abc import IJobRunner
from plainbox.impl.result import JobResult

logger = logging.getLogger("plainbox.runner")


class _IOLogBuilder(extcmd.DelegateBase):
    """
    Delegate for extcmd that build a log of all the data that was written by a
    process in a format expected by IJobResult.io_log. The format is a sequence
    of tuples (delay, stream_name, data).
    """

    def __init__(self):
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
        record = (delay.total_seconds(), stream_name, line)
        self.io_log.append(record)
        logger.debug("io log captured %r", record)


class CommandOutputLogger(extcmd.DelegateBase):

    def __init__(self, prompt):
        self._prompt = prompt
        self._lineno = collections.defaultdict(int)

    def on_line(self, stream_name, line):
        self._lineno[stream_name] += 1
        print("(job {}, <{}:{:05}>) {}".format(
            self._prompt, stream_name, self._lineno[stream_name],
            line.rstrip()))


class JobRunner(IJobRunner):

    def __init__(self, checkbox, session_dir, command_io_delegate=None,
                 outcome_callback=None):
        """
        Initialize a new job runner.

        Uses the specified CheckBox instance to execute scripts. Uses the
        specified session_dir as CHECKBOX_DATA environment variable. Uses the
        specified IO delegate for extcmd.ExternalCommandWithDelegate to track
        IO done by the called commands (optional, a simple console printer is
        provided if missing).
        """
        self._checkbox = checkbox
        self._session_dir = session_dir
        self._command_io_delegate = command_io_delegate
        self._outcome_callback = outcome_callback

    def run_job(self, job):
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
            return runner(job)

    def _plugin_shell(self, job):
        return self._just_run_command(job)

    def _plugin_resource(self, job):
        return self._just_run_command(job)

    def _plugin_local(self, job):
        return self._just_run_command(job)

    def _plugin_manual(self, job):
        if self._outcome_callback is None:
            return JobResult({
                'job': job,
                'outcome': JobResult.OUTCOME_SKIP,
                'comment': "non-interactive test run"
            })
        else:
            result = self._just_run_command(job)
            # XXX: make outcome writable
            result._data['outcome'] = self._outcome_callback()
            return result

    def _just_run_command(self, job):
        # Run the embedded command
        return_code, io_log = self._run_command(job)
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

    def _get_checkbox_script_env(self, job):
        """
        Create an environment suitable for executing CheckBox scripts.

        This environment has additional PATH, PYTHONPATH entries. It also uses
        fixed LANG so that scripts behave as expected. Lastly it sets
        CHECKBOX_SHARE that is required by some scripts.
        """
        # Get a proper environment
        env = dict(os.environ)
        # Use non-internationalized environment
        env['LANG'] = 'C.UTF-8'
        # Use PATH that can lookup checkbox scripts
        if self._checkbox.extra_PYTHONPATH:
            env['PYTHONPATH'] = os.pathsep.join(
                [self._checkbox.extra_PYTHONPATH]
                + os.getenv("PYTHONPATH", "").split(os.pathsep))
        # Update PATH so that scripts can be found
        env['PATH'] = os.pathsep.join(
            [self._checkbox.extra_PATH]
            + os.getenv("PATH", "").split(os.pathsep))
        # Add CHECKBOX_SHARE that is needed by one script
        env['CHECKBOX_SHARE'] = self._checkbox.CHECKBOX_SHARE
        # Add CHECKBOX_DATA (temporary checkbox data)
        assert self._session_dir is not None
        env['CHECKBOX_DATA'] = self._session_dir
        return env

    def _run_command(self, job):
        """
        Run the shell command associated with the specified job.

        Returns a tuple (return_code, io_log)
        """
        ui_io_delegate = self._command_io_delegate
        # If there is no UI delegate specified create a simple
        # delegate that logs all output to the console
        if ui_io_delegate is None:
            ui_io_delegate = CommandOutputLogger(job.name)
        # Create a delegate that builds a log of all IO
        io_log_builder = _IOLogBuilder()
        # Create a subprocess.Popen() like object that uses the
        # delegate system to observe all IO as it occurs in real
        # time.
        logging_popen = extcmd.ExternalCommandWithDelegate(
            extcmd.Decode(extcmd.Chain([io_log_builder, ui_io_delegate])))
        # Start the process and wait for it to finish getting the
        # result code. This will actually call a number of callbacks
        # while the process is running. It will also spawn a few
        # threads although all callbacks will be fired from a single
        # thread (which is _not_ the main thread)
        return_code = logging_popen.call(
            # XXX: sadly using /bin/sh results in broken output
            # XXX: maybe run it both ways and raise exceptions on differences?
            ['bash', '-c', job.command],
            env=self._get_checkbox_script_env(job))
        logger.debug("%s command return code: %r",
                     job.name, return_code)
        # XXX: Perhaps handle process dying from signals here
        # When the process is killed proc.returncode is not set
        # and another (cannot remember now) attribute is set
        return return_code, io_log_builder.io_log
