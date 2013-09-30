# This file is part of Checkbox.
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
:mod:`plainbox.impl.commands.analyze` -- analyze sub-command
============================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from logging import getLogger
from datetime import timedelta

from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.session import SessionStateLegacyAPI as SessionState
from plainbox.impl.runner import JobRunner


logger = getLogger("plainbox.commands.special")


class AnalyzeInvocation(CheckBoxInvocationMixIn):

    def __init__(self, provider, ns):
        super(AnalyzeInvocation, self).__init__(provider)
        self.ns = ns
        self.job_list = self.get_job_list(ns)
        self.desired_job_list = self._get_matching_job_list(ns, self.job_list)
        self.session = SessionState(self.job_list)
        self.problem_list = self.session.update_desired_job_list(
            self.desired_job_list)

    def run(self):
        if self.ns.run_local:
            self._run_local_jobs()
        if self.ns.print_stats:
            self._print_general_stats()
        if self.ns.print_dependency_report:
            self._print_dependency_report()
        if self.ns.print_interactivity_report:
            self._print_interactivity_report()
        if self.ns.print_estimated_duration_report:
            self._print_estimated_duration_report()
        if self.ns.print_validation_report:
            self._print_validation_report(self.ns.only_errors)

    def _run_local_jobs(self):
        print("[Running Local Jobs]".center(80, '='))
        with self.session.open():
            runner = JobRunner(
                self.session.session_dir, self.session.jobs_io_log_dir,
                command_io_delegate=self, interaction_callback=None)
            again = True
            while again:
                for job in self.session.run_list:
                    if job.plugin == 'local':
                        if self.session.job_state_map[job.name].result.outcome is None:
                            self._run_local_job(runner, job)
                            break
                else:
                    again = False

    def _run_local_job(self, runner, job):
        print("{job}".format(job=job.name))
        result = runner.run_job(job)
        self.session.update_job_result(job, result)
        new_desired_job_list = self._get_matching_job_list(
            self.ns, self.session.job_list)
        new_problem_list = self.session.update_desired_job_list(
            new_desired_job_list)
        if new_problem_list:
            print("Problem list", new_problem_list)
            self.problem_list.extend(new_problem_list)

    def _print_general_stats(self):
        print("[General Statistics]".center(80, '='))
        print("Known jobs: {}".format(len(self.job_list)))
        print("Selected jobs: {}".format(len(self.desired_job_list)))

    def _print_dependency_report(self):
        print("[Dependency Report]".center(80, '='))
        if self.problem_list:
            for problem in self.problem_list:
                print(" * {}".format(problem))
        else:
            print("Selected jobs have no dependency problems")

    def _print_interactivity_report(self):
        print("[Interactivity Report]".center(80, '='))
        if not self.session.run_list:
            return
        max_job_len = max(len(job.name) for job in self.session.run_list)
        fmt = "{{job:{}}} : {{interactive:11}} : {{duration}}".format(
            max_job_len)
        for job in self.session.run_list:
            print(
                fmt.format(
                    job=job.name,
                    interactive=(
                        "automatic" if job.automated else "interactive"),
                    duration=(
                        timedelta(seconds=job.estimated_duration)
                        if job.estimated_duration is not None
                        else "unknown")
                )
            )

    def _print_estimated_duration_report(self):
        print("[Estimated Duration Report]".center(80, '='))
        print("Estimated test duration:")
        automated, manual = self.session.get_estimated_duration()
        print("   automated tests: {}".format(
            timedelta(seconds=automated) if automated is not None
            else "cannot estimate"))
        print("      manual tests: {}".format(
            timedelta(seconds=manual) if manual is not None
            else "cannot estimate"))
        print("             total: {}".format(
            timedelta(seconds=manual + automated)
            if manual is not None and automated is not None
            else "cannot estimate"))

    def _print_validation_report(self, only_errors):
        print("[Validation Report]".center(80, '='))
        if not self.session.run_list:
            return
        max_job_len = max(len(job.name) for job in self.session.run_list)
        fmt = "{{job:{}}} : {{problem}}".format(max_job_len)
        problem = None
        for job in self.session.run_list:
            try:
                job.validate()
            except ValueError as exc:
                problem = str(exc)
            else:
                if only_errors:
                    continue
                problem = ""
            print(fmt.format(job=job.name, problem=problem))
        if only_errors and problem is None:
            print("No problems found")


class AnalyzeCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Implementation of ``$ plainbox dev analyze``
    """

    def __init__(self, provider):
        self.provider = provider

    def invoked(self, ns):
        return AnalyzeInvocation(self.provider, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "analyze", help="analyze how selected jobs would be executed")
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '-l', '--run-local',
            action='store_true', dest='run_local',
            help='Run all selected local jobs, required to see true data')
        group.add_argument(
            '-L', '--skip-local',
            action='store_false', dest='run_local',
            help='Do not run local jobs')
        group = parser.add_argument_group("reports")
        group.add_argument(
            '-s', '--print-stats', action='store_true',
            help="Print general job statistics")
        group.add_argument(
            "-d", "--print-dependency-report", action='store_true',
            help="Print dependency report")
        group.add_argument(
            "-t", "--print-interactivity-report", action='store_true',
            help="Print interactivity report")
        group.add_argument(
            "-e", "--print-estimated-duration-report", action='store_true',
            help="Print estimated duration report")
        group.add_argument(
            "-v", "--print-validation-report", action='store_true',
            help="Print validation report")
        group.add_argument(
            "-E", "--only-errors", action='store_true', default=False,
            help="When coupled with -v, only problematic jobs will be listed")
        parser.set_defaults(command=self)
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
