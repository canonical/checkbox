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
from logging import getLogger
import os

from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.result import JobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.session import SessionState
from plainbox.impl.exporter.xml import XMLSessionStateExporter
from plainbox.impl.checkbox import CheckBox, WhiteList
from plainbox.impl.applogic import get_matching_job_list


logger = getLogger("plainbox.commands.sru")


class _SRUInvocation:
    """
    Helper class instantiated to perform a particular invocation of the sru
    command. Unlike the SRU command itself, this class is instantiated each
    time.
    """

    def __init__(self, ns):
        self.ns = ns
        self.checkbox = CheckBox()
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
            self._save_results()
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
        print("Saving results to {0}".format(self.ns.fallback_file))
        data = self.exporter.get_session_data_subset(self.session)
        with open(self.ns.fallback_file, "wt", encoding="UTF-8") as stream:
            self.exporter.dump(data, stream)

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
        if job_state.can_start() or False:
            job_result = self.runner.run_job(job)
        else:
            job_result = JobResult({
                'job': job,
                'outcome': JobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
        assert job_result is not None
        print("{0}".format(job_result.outcome))
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

    def invoked(self, ns):
        # a list of todos from functionality point of view:
        # TODO: instantiate the 'c4' transport/stream wrapper
        # TODO: try sending stuff to c4
        # TODO: if that fails save the result on disk and bail
        # a list of todos from implementation point of view:
        # TODO: refactor box.py so that running tests with simple
        #       gui is a reusable component that can be used both
        #       for 'sru' and 'run' command.
        # TODO: update docs on sru command
        return _SRUInvocation(ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "sru", help="run automated stable release update tests")
        parser.set_defaults(command=self)
        parser.add_argument(
            'secure_id', metavar="SECURE-ID",
            action='store',
            help=("Associate submission with a machine using this SECURE-ID"))
        parser.add_argument(
            'fallback_file', metavar="FALLBACK-FILE",
            action='store',
            help=("If submission fails save the test report as FALLBACK-FILE"))
        parser.add_argument(
            '--destination', metavar="URL",
            action='store',
            default="https://certification.canonical.com/submissions/submit/",
            help=("POST the test report XML to this URL"))
