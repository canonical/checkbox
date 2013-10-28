# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.secure.checkbox_trusted_launcher` -- command launcher
=========================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import argparse
import glob
import os
import subprocess

from plainbox.impl.secure.rfc822 import load_rfc822_records
from plainbox.impl.secure.job import BaseJob


class Runner:
    """
    Runner for jobs

    Executes the command process and pipes back stdout/stderr
    """

    CHECKBOXES = "/usr/share/checkbox*"

    def __init__(self, builtin_jobs=[], packages=[]):
        # List of all available jobs in system-wide locations
        self.builtin_jobs = builtin_jobs
        # List of all checkbox variants, like checkbox-oem(-.*)?
        self.packages = packages

    def path_expand(self, path):
        for p in glob.glob(path):
            self.packages.append(p)
            for dirpath, dirs, filenames in os.walk(os.path.join(p, 'jobs')):
                for name in filenames:
                    if name.endswith(".txt"):
                        yield os.path.join(dirpath, name)

    def main(self, argv=None):
        parser = argparse.ArgumentParser(prog="checkbox-trusted-launcher")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--hash', metavar='HASH', help='job hash to match')
        group.add_argument(
            '--warmup',
            action='store_true',
            help='Return immediately, only useful when used with pkexec(1)')
        parser.add_argument(
            '--via',
            metavar='LOCAL-JOB-HASH',
            dest='via_hash',
            help='Local job hash to use to match the generated job')
        parser.add_argument(
            'ENV', metavar='NAME=VALUE', nargs='*',
            help='Set each NAME to VALUE in the string environment')
        args = parser.parse_args(argv)

        if args.warmup:
            return 0

        for filename in self.path_expand(self.CHECKBOXES):
            stream = open(filename, "r", encoding="utf-8")
            for message in load_rfc822_records(stream):
                self.builtin_jobs.append(BaseJob(message.data))
            stream.close()
        lookup_list = [j for j in self.builtin_jobs if j.user]

        args.ENV = dict(item.split('=') for item in args.ENV)

        if args.via_hash is not None:
            local_list = [j for j in self.builtin_jobs if j.plugin == 'local']
            desired_job_list = [j for j in local_list
                                if j.checksum == args.via_hash]
            if desired_job_list:
                via_job = desired_job_list.pop()
                via_job_result = subprocess.Popen(
                    ['bash', '-c', via_job.command],
                    universal_newlines=True,
                    stdout=subprocess.PIPE,
                    env=via_job.modify_execution_environment(
                        args.ENV,
                        self.packages)
                )
                try:
                    for message in load_rfc822_records(via_job_result.stdout):
                        lookup_list.append(BaseJob(message.data))
                finally:
                    # Always call Popen.wait() in order to avoid zombies
                    via_job_result.stdout.close()
                    via_job_result.wait()

        try:
            target_job = [j for j in lookup_list
                          if j.checksum == args.hash][0]
        except IndexError:
            return "Job not found"
        try:
            os.execve(
                '/bin/bash',
                ['bash', '-c', target_job.command],
                target_job.modify_execution_environment(
                    args.ENV,
                    self.packages)
            )
        # if execve doesn't fail, it never returns...
        except OSError:
            return "Fatal error"
        finally:
            return "Fatal error"


def main(argv=None):
    """
    Entry point for the checkbox trusted launcher
    """
    runner = Runner()
    raise SystemExit(runner.main(argv))
