# This file is part of Checkbox.
#
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
:mod:`plainbox.impl.commands.sru` -- sru sub-command
====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
import logging
import os

from requests.exceptions import ConnectionError, InvalidSchema, HTTPError

from plainbox.impl.applogic import get_matching_job_list
from plainbox.impl.checkbox import CheckBox, WhiteList
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.config import ValidationError, Unset
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter.xml import XMLSessionStateExporter
from plainbox.impl.result import JobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.session import SessionState
from plainbox.impl.transport.certification import CertificationTransport
from plainbox.impl.transport.certification import InvalidSecureIDError


logger = logging.getLogger("plainbox.commands.sru")


class _SRUInvocation:
    """
    Helper class instantiated to perform a particular invocation of the sru
    command. Unlike the SRU command itself, this class is instantiated each
    time.
    """

    def __init__(self, ns, config):
        self.ns = ns
        self.checkbox = CheckBox()
        self.config = config
        self.whitelist = WhiteList.from_file(os.path.join(
            self.checkbox.whitelists_dir, "sru.whitelist"))
        self.job_list = self.checkbox.get_builtin_jobs()
        # XXX: maybe allow specifying system_id from command line?
        self.exporter = XMLSessionStateExporter(system_id=None)
        self.session = None
        self.runner = None

    def run(self):
        # Compute the run list, this can give us notification about problems in
        # the selected jobs. Currently we just display each problem
        # Create a session that handles most of the stuff needed to run jobs
        try:
            self.session = SessionState(self.job_list)
        except DependencyDuplicateError as exc:
            # Handle possible DependencyDuplicateError that can happen if
            # someone is using plainbox for job development.
            print("The job database you are currently using is broken")
            print("At least two jobs contend for the name {0}".format(
                exc.job.name))
            print("First job defined in: {0}".format(exc.job.origin))
            print("Second job defined in: {0}".format(
                exc.duplicate_job.origin))
            raise SystemExit(exc)
        with self.session.open():
            self._set_job_selection()
            self.runner = JobRunner(
                self.session.session_dir,
                self.session.jobs_io_log_dir,
                command_io_delegate=self,
                outcome_callback=None)  # SRU runs are never interactive
            self._run_all_jobs()
            if self.config.fallback_file is not Unset:
                self._save_results()
            self._submit_results()
        # FIXME: sensible return value
        return 0

    def _set_job_selection(self):
        desired_job_list = get_matching_job_list(self.job_list, self.whitelist)
        problem_list = self.session.update_desired_job_list(desired_job_list)
        if problem_list:
            logger.warning("There were some problems with the selected jobs")
            for problem in problem_list:
                logger.warning("- %s", problem)
            logger.warning("Problematic jobs will not be considered")

    def _save_results(self):
        print("Saving results to {0}".format(self.config.fallback_file))
        data = self.exporter.get_session_data_subset(self.session)
        with open(self.config.fallback_file, "wt", encoding="UTF-8") as stream:
            translating_stream = ByteStringStreamTranslator(stream, "UTF-8")
            self.exporter.dump(data, translating_stream)

    def _submit_results(self):
        print("Submitting results to {0} for secure_id {1}".format(
              self.config.c3_url, self.config.secure_id))
        options_string = "secure_id={0}".format(self.config.secure_id)
        try:
            transport = CertificationTransport(
                self.config.c3_url, options_string)
        except InvalidSecureIDError as exc:
            print(exc)
            return False
        try:
            with open(self.config.fallback_file, "rt",
                      encoding="UTF-8") as stream:
                result = transport.send(stream)
                print("Successfully sent, server gave me id {0}".format(
                      result['id']))
        except IOError as exc:
            print("Problem reading a file: {0}".format(exc))
        except InvalidSchema as exc:
            print("Invalid destination URL: {0}".format(exc))
        except ConnectionError as exc:
            print("Unable to connect to destination URL: {0}".format(exc))
        except HTTPError as exc:
            print(("Server returned an error when "
                   "receiving or processing: {0}").format(exc))

    def _run_all_jobs(self):
        again = True
        while again:
            again = False
            for job in self.session.run_list:
                # Skip jobs that already have result, this is only needed when
                # we run over the list of jobs again, after discovering new
                # jobs via the local job output
                result = self.session.job_state_map[job.name].result
                if result.outcome is not None:
                    continue
                self._run_single_job(job)
                self.session.persistent_save()
                if job.plugin == "local":
                    # After each local job runs rebuild the list of matching
                    # jobs and run everything again
                    self._set_job_selection()
                    again = True
                    break

    def _run_single_job(self, job):
        print("- {}:".format(job.name), end=' ')
        job_state = self.session.job_state_map[job.name]
        if job_state.can_start():
            if (self.ns.dry_run and job.plugin not in (
                    'local', 'resource', 'attachment')):
                job_result = JobResult({
                    'job': job,
                    'outcome': JobResult.OUTCOME_SKIP,
                    'comments': "Job skipped in dry-run mode"
                })
            else:
                job_result = self.runner.run_job(job, self.config)
        else:
            # Set the outcome of jobs that cannot start to
            # OUTCOME_NOT_SUPPORTED _except_ if any of the inhibitors point to
            # a job with an OUTCOME_SKIP outcome, if that is the case mirror
            # that outcome. This makes 'skip' stronger than 'not-supported'
            outcome = JobResult.OUTCOME_NOT_SUPPORTED
            for inhibitor in job_state.readiness_inhibitor_list:
                if inhibitor.cause != inhibitor.FAILED_DEP:
                    continue
                related_job_state = self.session.job_state_map[
                    inhibitor.related_job.name]
                if related_job_state.result.outcome == JobResult.OUTCOME_SKIP:
                    outcome = JobResult.OUTCOME_SKIP
            job_result = JobResult({
                'job': job,
                'outcome': outcome,
                'comments': job_state.get_readiness_description()
            })
        assert job_result is not None
        print("{0}".format(job_result.outcome))
        if job_result.comments is not None:
            print("comments: {0}".format(job_result.comments))
        if job_state.readiness_inhibitor_list:
            print("inhibitors:")
        for inhibitor in job_state.readiness_inhibitor_list:
            print("  * {}".format(inhibitor))
        self.session.update_job_result(job, job_result)


class SRUCommand(PlainBoxCommand):
    """
    Command for running Stable Release Update (SRU) tests.

    Stable release updates are periodic fixes for nominated bugs that land in
    existing supported Ubuntu releases. To ensure a certain level of quality
    all SRU updates affecting hardware enablement are automatically tested
    on a pool of certified machines.

    This command is _temporary_ and will eventually migrate to the checkbox
    side. Its intended lifecycle is for the development and validation of
    plainbox core on realistic workloads.
    """

    def __init__(self, config):
        self.config = config

    def invoked(self, ns):
        # Copy command-line arguments over configuration variables
        try:
            if ns.secure_id:
                self.config.secure_id = ns.secure_id
            if ns.fallback_file and ns.fallback_file is not Unset:
                self.config.fallback_file = ns.fallback_file
            if ns.c3_url:
                self.config.c3_url = ns.c3_url
        except ValidationError as exc:
            print("Configuration problems prevent running SRU tests")
            print(exc)
            return 1
        return _SRUInvocation(ns, self.config).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "sru", help="run automated stable release update tests")
        parser.set_defaults(command=self)
        group = parser.add_argument_group("sru-specific options")
        # Set defaults from based on values from the config file
        group.set_defaults(
            secure_id=self.config.secure_id,
            c3_url=self.config.c3_url,
            fallback_file=self.config.fallback_file)
        group.add_argument(
            '--secure-id', metavar="SECURE-ID",
            action='store',
            # NOTE: --secure-id is optional only when set in a config file
            required=self.config.secure_id is Unset,
            help=("Associate submission with a machine using this SECURE-ID"
                  " (%(default)s)"))
        group.add_argument(
            '--fallback', metavar="FILE",
            dest='fallback_file',
            action='store',
            default=Unset,
            help=("If submission fails save the test report as FILE"
                  " (%(default)s)"))
        group.add_argument(
            '--destination', metavar="URL",
            dest='c3_url',
            action='store',
            help=("POST the test report XML to this URL"
                  " (%(default)s)"))
        group = parser.add_argument_group(title="execution options")
        group.add_argument(
            '-n', '--dry-run',
            action='store_true',
            default=False,
            help=("Skip all usual jobs."
                  " Only local, resource and attachment jobs are started"))
