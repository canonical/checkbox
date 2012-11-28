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

from io import StringIO
import logging
import os
import shutil
import subprocess
import tempfile

from plainbox.abc import IJobRunner
from plainbox.impl.result import JobResult
from plainbox.impl.resource import Resource
from plainbox.impl.rfc822 import RFC822SyntaxError
from plainbox.impl.rfc822 import load_rfc822_records

logger = logging.getLogger("plainbox.runner")


class Scratch:
    """
    Context manager for having a temporary directory that gets wiped later

    Used to give value to CHECKBOX_DATA.
    """

    def __init__(self):
        self.pathname = None

    def __enter__(self):
        self.pathname = tempfile.mkdtemp()
        return self

    def __exit__(self, *args):
        shutil.rmtree(self.pathname)
        self.pathname = None


class JobRunner(IJobRunner):

    def __init__(self, checkbox, context, scratch):
        """
        Initialize a new job runner.

        Use the specified CheckBox instance to execute scripts
        Use the specified ResourceContext to manage resources
        Use the specified Scratch directory manager
        """
        # XXX: this is somewhat crappy as scratch needs to be managed outside
        # of this class. It would be better to have it managed internally but
        # it would itself become a context manager which is undesirable due to
        # the complexity.
        self._checkbox = checkbox
        self._context = context
        self._scratch = scratch

    def run_job(self, job):
        logger.info("Running %r", job)
        func_name = "_plugin_" + job.plugin.replace('-', '_')
        try:
            runner = getattr(self, func_name)
        except AttributeError:
            raise ValueError("Unsupported job plugin: {}".format(job.plugin))
        try:
            return runner(job)
        except NotImplementedError:
            return JobResult({
                'job': job,
                'outcome': JobResult.OUTCOME_NOT_IMPLEMENTED,
            })

    def _plugin_attachment(self, job):
        raise NotImplementedError("TODO: attachments")

    def _plugin_local(self, job):
        raise NotImplementedError("TODO: local")

    def _plugin_manual(self, job):
        raise NotImplementedError("TODO: manual")

    def _plugin_resource(self, job):
        proc = self._run_command(job)
        if proc.returncode == 127:
            logging.warning("Unable to find command: %s", job.command)
            return
        line_list = []
        for byte_line in proc.stdout.splitlines():
            try:
                line = byte_line.decode("UTF-8")
            except UnicodeDecodeError as exc:
                logger.warning("resource script %s returned invalid UTF-8 data"
                               " %r: %s", job, byte_line, exc)
            else:
                line_list.append(line)
        with StringIO("\n".join(line_list)) as stream:
            try:
                record_list = load_rfc822_records(stream)
            except RFC822SyntaxError as exc:
                logger.warning("resource script %s returned invalid RFC822"
                               " data: %s", job, exc)
            else:
                for record in record_list:
                    logger.info("Storing resource record %s: %s",
                                job.name, record)
                    resource = Resource(record)
                    self._context.add_resource(job.name, resource)

    def _plugin_shell(self, job):
        """
        Implementation of a job runner for the 'shell' plugin
        """
        proc = self._run_command(job)
        # Convert the return of the command to the outcome of the job
        if getattr(proc, 'returncode') == 0:
            outcome = JobResult.OUTCOME_PASS
        else:
            outcome = JobResult.OUTCOME_FAIL
        # Create a result object and return it
        return JobResult({
            'job': job,
            'outcome': outcome,
            'comments': None,
            'io_log': None,  # TODO: implement this
            'return_code': getattr(proc, 'returncode', 'Killed by signal')
        })

    def _plugin_user_interact(self, job):
        raise NotImplementedError("TODO: interact")

    def _plugin_user_verify(self, job):
        raise NotImplementedError("TODO: verify")

    def _get_checkbox_script_env(self):
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
        assert self._scratch.pathname is not None
        env['CHECKBOX_DATA'] = self._scratch.pathname
        return env

    def _run_command(self, job):
        """
        Run the shell command associated with the specified job.

        Returns a subprocess.Popen object. The object is slightly
        modified so that .stdout and .stderr are the actual output
        strings.
        """
        # TODO: Grab detailed IO log as required by TestResult.io_log. We can
        # use extcmd from pypi for this, it needs to be ported to python3
        # Start the process, capturing stdout and stderr
        proc = subprocess.Popen(
            # XXX: sadly using /bin/sh results in broken output
            # XXX: maybe run it both ways and raise exceptions on differences?
            ['bash', '-c', job.command],
            env=self._get_checkbox_script_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Run to completion
        stdout, stderr = proc.communicate()
        proc.stdout = stdout
        proc.stderr = stderr
        logger.debug("%s command stdout: %r", job.name, proc.stdout)
        logger.debug("%s command stderr: %r", job.name, proc.stderr)
        logger.debug("%s command return code: %r",
                     job.name, proc.returncode)
        # XXX: Perhaps handle process dying from signals here
        # When the process is killed proc.returncode is not set
        # and another (cannot remember now) attribute is set
        return proc
