# This file is part of Checkbox.
#
# Copyright 2012-2013 Canonical Ltd.
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
:mod:`plainbox.impl.commands.run` -- run sub-command
====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import FileType
from logging import getLogger
from os.path import join
import sys

from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.result import JobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import slugify
from plainbox.impl.session import SessionState


logger = getLogger("plainbox.commands.run")


class RunCommand(PlainBoxCommand, CheckBoxCommandMixIn):

    def invoked(self, ns):
        if ns.output_format == '?':
            self._print_output_format_list(ns)
            return 0
        elif ns.output_options == '?':
            self._print_output_option_list(ns)
            return 0
        else:
            exporter = self._prepare_exporter(ns)
            job_list = self.get_job_list(ns)
            return self._run_jobs(ns, job_list, exporter)

    def register_parser(self, subparsers):
        parser = subparsers.add_parser("run", help="run a test job")
        parser.set_defaults(command=self)
        group = parser.add_argument_group(title="user interface options")
        group.add_argument(
            '--not-interactive', action='store_true',
            help="Skip tests that require interactivity")
        group.add_argument(
            '-n', '--dry-run', action='store_true',
            help="Don't actually run any jobs")
        group = parser.add_argument_group("output options")
        assert 'text' in get_all_exporters()
        group.add_argument(
            '-f', '--output-format', default='text',
            metavar='FORMAT', choices=['?'] + list(
                get_all_exporters().keys()),
            help=('Save test results in the specified FORMAT'
                  ' (pass ? for a list of choices)'))
        group.add_argument(
            '-p', '--output-options', default='',
            metavar='OPTIONS',
            help=('Comma-separated list of options for the export mechanism'
                  ' (pass ? for a list of choices)'))
        group.add_argument(
            '-o', '--output-file', default='-',
            metavar='FILE', type=FileType("wb"),
            help=('Save test results to the specified FILE'
                  ' (or to stdout if FILE is -)'))
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)

    def _print_output_format_list(self, ns):
        print("Available output formats: {}".format(
            ', '.join(get_all_exporters())))

    def _print_output_option_list(self, ns):
        print("Each format may support a different set of options")
        for name, exporter_cls in get_all_exporters().items():
            print("{}: {}".format(
                name, ", ".join(exporter_cls.supported_option_list)))

    def _prepare_exporter(self, ns):
        exporter_cls = get_all_exporters()[ns.output_format]
        if ns.output_options:
            option_list = ns.output_options.split(',')
        else:
            option_list = None
        try:
            exporter = exporter_cls(option_list)
        except ValueError as exc:
            raise SystemExit(str(exc))
        return exporter

    def ask_for_resume(self, prompt=None, allowed=None):
        # FIXME: Add support/callbacks for a GUI
        if prompt is None:
            prompt = "Do you want to resume the previous session [Y/n]? "
        if allowed is None:
            allowed = ('', 'y', 'Y', 'n', 'N')
        answer = None
        while answer not in allowed:
            answer = input(prompt)
        return False if answer in ('n', 'N') else True

    def _run_jobs(self, ns, job_list, exporter):
        # Compute the run list, this can give us notification about problems in
        # the selected jobs. Currently we just display each problem
        matching_job_list = self._get_matching_job_list(ns, job_list)
        print("[ Analyzing Jobs ]".center(80, '='))
        # Create a session that handles most of the stuff needed to run jobs
        try:
            session = SessionState(job_list)
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
        with session.open():
            if session.previous_session_file():
                if self.ask_for_resume():
                    session.resume()
                else:
                    session.clean()
            self._update_desired_job_list(session, matching_job_list)
            if (sys.stdin.isatty() and sys.stdout.isatty() and not
                    ns.not_interactive):
                outcome_callback = self.ask_for_outcome
            else:
                outcome_callback = None
            runner = JobRunner(session.session_dir,
                               session.jobs_io_log_dir,
                               outcome_callback=outcome_callback)
            self._run_jobs_with_session(ns, session, runner)
            self._save_results(ns, session, exporter)
        # FIXME: sensible return value
        return 0

    def _save_results(self, ns, session, exporter):
        data = exporter.get_session_data_subset(session)
        if ns.output_file is sys.stdout:
            print("[ Results ]".center(80, '='))
            #This requires a bit more finesse, as exporters output bytes
            #and stdout needs a string.
            translating_stream = ByteStringStreamTranslator(
                ns.output_file, "UTF-8")
            exporter.dump(data, translating_stream)
        else:
            print("Saving results to {}".format(ns.output_file.name))
            with ns.output_file as stream:
                exporter.dump(data, stream)

    def ask_for_outcome(self, prompt=None, allowed=None):
        if prompt is None:
            prompt = "what is the outcome? "
        if allowed is None:
            allowed = (JobResult.OUTCOME_PASS,
                       JobResult.OUTCOME_FAIL,
                       JobResult.OUTCOME_SKIP)
        answer = None
        while answer not in allowed:
            print("Allowed answers are: {}".format(", ".join(allowed)))
            answer = input(prompt)
        return answer

    def _update_desired_job_list(self, session, desired_job_list):
        problem_list = session.update_desired_job_list(desired_job_list)
        if problem_list:
            print("[ Warning ]".center(80, '*'))
            print("There were some problems with the selected jobs")
            for problem in problem_list:
                print(" * {}".format(problem))
            print("Problematic jobs will not be considered")

    def _run_jobs_with_session(self, ns, session, runner):
        # TODO: run all resource jobs concurrently with multiprocessing
        # TODO: make local job discovery nicer, it would be best if
        # desired_jobs could be managed entirely internally by SesionState. In
        # such case the list of jobs to run would be changed during iteration
        # but would be otherwise okay).
        print("[ Running All Jobs ]".center(80, '='))
        again = True
        while again:
            again = False
            for job in session.run_list:
                # Skip jobs that already have result, this is only needed when
                # we run over the list of jobs again, after discovering new
                # jobs via the local job output
                if session.job_state_map[job.name].result.outcome is not None:
                    continue
                self._run_single_job_with_session(ns, session, runner, job)
                session.persistent_save()
                if job.plugin == "local":
                    # After each local job runs rebuild the list of matching
                    # jobs and run everything again
                    new_matching_job_list = self._get_matching_job_list(
                        ns, session.job_list)
                    self._update_desired_job_list(
                        session, new_matching_job_list)
                    again = True
                    break

    def _run_single_job_with_session(self, ns, session, runner, job):
        print("[ {} ]".format(job.name).center(80, '-'))
        if job.description is not None:
            print(job.description)
            print("^" * len(job.description.splitlines()[-1]))
            print()
        job_state = session.job_state_map[job.name]
        logger.debug("Job name: %s", job.name)
        logger.debug("Plugin: %s", job.plugin)
        logger.debug("Direct dependencies: %s", job.get_direct_dependencies())
        logger.debug("Resource dependencies: %s",
                     job.get_resource_dependencies())
        logger.debug("Resource program: %r", job.requires)
        logger.debug("Command: %r", job.command)
        logger.debug("Can start: %s", job_state.can_start())
        logger.debug("Readiness: %s", job_state.get_readiness_description())
        if job_state.can_start():
            if ns.dry_run:
                print("Not really running anything in dry-run mode")
                job_result = JobResult({
                    'job': job,
                    'outcome': 'dry-run',
                })
            else:
                print("Running... (output in {}.*)".format(
                    join(session.jobs_io_log_dir, slugify(job.name))))
                job_result = runner.run_job(job)
                print("Outcome: {}".format(job_result.outcome))
                print("Comments: {}".format(job_result.comments))
        else:
            job_result = JobResult({
                'job': job,
                'outcome': JobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
        if job_result is None and not ns.dry_run:
            logger.warning("Job %s did not return a result", job)
        if job_result is not None:
            session.update_job_result(job, job_result)
