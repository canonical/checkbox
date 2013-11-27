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
:mod:`plainbox.impl.secure.launcher1` -- plainbox-trusted-launcher-1
====================================================================
"""

import argparse
import subprocess

from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.providers.v1 import all_providers
from plainbox.impl.secure.rfc822 import load_rfc822_records


class TrustedLauncher:
    """
    Trusted Launcher for v1 jobs.
    """

    def __init__(self):
        """
        Initialize a new instance of the trusted launcher
        """
        self._job_list = []

    def add_job_list(self, job_list):
        """
        Add jobs to the trusted launcher
        """
        self._job_list.extend(job_list)

    def find_job(self, checksum):
        for job in self._job_list:
            if job.checksum == checksum:
                return job
        else:
            raise LookupError(
                "Cannot find job with checksum {}".format(checksum))

    def run_shell_from_job(self, checksum, env):
        """
        Run a job with the given checksum.

        :param checksum:
            The checksum of the job to execute.
        :param env:
            Environment to execute the job in.
        :returns:
            The return code of the command
        :raises LookupError:
            If the checksum does not match any known job
        """
        job = self.find_job(checksum)
        cmd = ['bash', '-c', job.command]
        return subprocess.call(cmd, env=env)

    def run_local_job(self, checksum):
        """
        Run a job with and interpret the stdout as a job definition.

        :param checksum:
            The checksum of the job to execute
        :returns:
            A list of job definitions that were parsed out of the output.
        :raises LookupError:
            If the checksum does not match any known job
        """
        job = self.find_job(checksum)
        cmd = ['bash', '-c', job.command]
        output = subprocess.check_output(cmd, universal_newlines=True)
        job_list = []
        record_list = load_rfc822_records(output)
        for record in record_list:
            job = JobDefinition.from_rfc822_record(record)
            job_list.append(job)
        return job_list


def main(argv=None):
    """
    Entry point for the plainbox-trusted-launcher-1

    :param argv:
        Command line arguments to parse. If None (default) then sys.argv is
        used instead.

    :returns:
        The return code of the job that was selected with the --hash argument
        or zero if the --warmup argument was specified.
    :raises:
        SystemExit if --hash or --via point to unknown jobs.

    The trusted launcher is a sudo-like program, that can grant unprivileged
    users permission to run something as root, that is restricted to executing
    shell snippets embedded inside job definitions offered by v1 plainbox
    providers.

    As a security measure the trusted launcher only considers job providers
    listed in the system-wide directory since one needs to be root to add
    additional definitions there anyway.

    Unlike the rest of plainbox, the trusted launcher does not produce job
    results, instead it just literally executes the shell snippet and returns
    stdout/stderr unaffected to the invoking process. The exception to this
    rule is the way --via argument is handled, where the trusted launcher needs
    to capture stdout to interpret that as job definitions.

    Unlike sudo, the trusted launcher is not a setuid program and cannot grant
    root access in itself. Instead it relies on a policykit and specifically on
    pkexec(1) alongside with an appropriate policy file, to grant users a way
    to run trusted-launcher as root (or another user).
    """
    parser = argparse.ArgumentParser(prog="plainbox-trusted-launcher-1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--hash',
        metavar='CHECKSUM',
        help='run a job with this checksum')
    group.add_argument(
        '--warmup',
        action='store_true',
        help='return immediately, only useful when used with pkexec(1)')
    parser.add_argument(
        '--via',
        metavar='CHECKSUM',
        dest='via',
        help='also run a job with this checksum (assuming it is a local job)')
    parser.add_argument(
        'env', metavar='NAME=VALUE', nargs='*',
        help='set each NAME to VALUE in the string environment')
    ns = parser.parse_args(argv)
    if ns.warmup:
        return 0
    else:
        # "parse environment"
        try:
            env = dict(item.split('=', 1) for item in ns.env)
        except ValueError:
            raise SystemExit(
                "environment definitions must use NAME=VALUE syntax")
        launcher = TrustedLauncher()
        # Siphon all jobs from all providers
        all_providers.load()
        for plugin in all_providers.get_all_plugins():
            launcher.add_job_list(
                plugin.plugin_object.get_builtin_jobs())
        # Run the local job and feed the result back to the launcher
        if ns.via:
            try:
                launcher.add_job_list(launcher.run_local_job(ns.via))
            except LookupError as exc:
                raise SystemExit(str(exc))
        # Run the target job and return the result code
        try:
            return launcher.run_shell_from_job(ns.hash, env)
        except LookupError as exc:
            raise SystemExit(str(exc))
