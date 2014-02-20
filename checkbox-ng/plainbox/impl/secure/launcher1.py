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
import copy
import logging
import subprocess

from plainbox.i18n import gettext as _
from plainbox.impl.job import JobDefinition
from plainbox.impl.job import JobOutputTextSource
from plainbox.impl.providers.special import CheckBoxSrcProvider
from plainbox.impl.secure.providers.v1 import all_providers
from plainbox.impl.secure.rfc822 import load_rfc822_records, RFC822SyntaxError


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
                _("Cannot find job with checksum {}").format(checksum))

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

    def run_local_job(self, checksum, env):
        """
        Run a job with and interpret the stdout as a job definition.

        :param checksum:
            The checksum of the job to execute
        :param env:
            Environment to execute the job in.
        :returns:
            A list of job definitions that were parsed out of the output.
        :raises LookupError:
            If the checksum does not match any known job
        """
        job = self.find_job(checksum)
        cmd = ['bash', '-c', job.command]
        output = subprocess.check_output(cmd, universal_newlines=True, env=env)
        job_list = []
        source = JobOutputTextSource(job)
        try:
            record_list = load_rfc822_records(output, source=source)
        except RFC822SyntaxError as exc:
            logging.error(
                _("Syntax error in job generated from %s: %s"), job, exc)
        else:
            for record in record_list:
                job = JobDefinition.from_rfc822_record(record)
                job_list.append(job)
        return job_list


class UpdateAction(argparse.Action):
    """
    Argparse action that builds up a dictionary.

    This action is similar to the built-in append action but it constructs
    a dictionary instead of a list.
    """

    def __init__(self, option_strings, dest, nargs=None, const=None,
                 default=None, type=None, choices=None, required=False,
                 help=None, metavar=None):
        if nargs == 0:
            raise ValueError('nargs for append actions must be > 0; if arg '
                             'strings are not supplying the value to append, '
                             'the append const action may be more appropriate')
        if const is not None and nargs != argparse.OPTIONAL:
            raise ValueError(
                'nargs must be {!r} to supply const'.format(argparse.OPTIONAL))
        super().__init__(
            option_strings=option_strings, dest=dest, nargs=nargs, const=const,
            default=default, type=type, choices=choices, required=required,
            help=help, metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        """
        Internal method of argparse.Action

        This method is invoked to "apply" the action after seeing all the
        values for a given argument. Please refer to argparse source code for
        information on how it is used.
        """
        items = copy.copy(argparse._ensure_value(namespace, self.dest, {}))
        for value in values:
            try:
                k, v = value.split('=', 1)
            except ValueError:
                raise argparse.ArgumentError(self, "expected NAME=VALUE")
            else:
                items[k] = v
        setattr(namespace, self.dest, items)


def main(argv=None):
    """
    Entry point for the plainbox-trusted-launcher-1

    :param argv:
        Command line arguments to parse. If None (default) then sys.argv is
        used instead.
    :returns:
        The return code of the job that was selected with the --target argument
        or zero if the --warmup argument was specified.
    :raises:
        SystemExit if --taget or --generator point to unknown jobs.

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
    parser.add_argument(
        '--development', action='store_true', help=argparse.SUPPRESS)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-w', '--warmup',
        action='store_true',
        # TRANSLATORS: don't translate pkexec(1)
        help=_('return immediately, only useful when used with pkexec(1)'))
    group.add_argument(
        '-t', '--target',
        metavar=_('CHECKSUM'),
        help=_('run a job with this checksum'))
    group = parser.add_argument_group(_("target job specification"))
    group.add_argument(
        '-T', '--target-environment', metavar=_('NAME=VALUE'),
        dest='target_env',
        nargs='+',
        action=UpdateAction,
        help=_('environment passed to the target job'))
    group = parser.add_argument_group(title=_("generator job specification"))
    group.add_argument(
        '-g', '--generator',
        metavar=_('CHECKSUM'),
        # TRANSLATORS: don't translate 'local' in the sentence below. It
        # denotes a special type of job, not its location.
        help=_(
            'also run a job with this checksum (assuming it is a local job)'))
    group.add_argument(
        '-G', '--generator-environment',
        dest='generator_env',
        nargs='+',
        metavar=_('NAME=VALUE'),
        action=UpdateAction,
        help=_('environment passed to the generator job'))
    ns = parser.parse_args(argv)
    # Just quit if warming up
    if ns.warmup:
        return 0
    launcher = TrustedLauncher()
    # Feed jobs into the trusted launcher
    if ns.development:
        # Use the checkbox source provider if requested via --development
        launcher.add_job_list(
            CheckBoxSrcProvider().get_builtin_jobs())
    else:
        # Siphon all jobs from all secure providers otherwise
        all_providers.load()
        for plugin in all_providers.get_all_plugins():
            launcher.add_job_list(
                plugin.plugin_object.get_builtin_jobs())
    # Run the local job and feed the result back to the launcher
    if ns.generator:
        try:
            generated_job_list = launcher.run_local_job(
                ns.generator, ns.generator_env)
            launcher.add_job_list(generated_job_list)
        except LookupError as exc:
            raise SystemExit(str(exc))
    # Run the target job and return the result code
    try:
        return launcher.run_shell_from_job(ns.target, ns.target_env)
    except LookupError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
