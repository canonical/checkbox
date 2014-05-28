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
:mod:`plainbox.impl.commands.analyze` -- analyze sub-command
============================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from datetime import timedelta
from logging import getLogger
import ast
import itertools
import os

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.resource import RequirementNodeVisitor
from plainbox.impl.runner import JobRunner
from plainbox.impl.session import SessionManager
from plainbox.impl.session import SessionMetaData
from plainbox.impl.session import SessionState


logger = getLogger("plainbox.commands.special")


class AnalyzeInvocation(CheckBoxInvocationMixIn):

    def __init__(self, provider_list, config, ns):
        super().__init__(provider_list, config)
        self.ns = ns
        self.unit_list = list(
            itertools.chain(*[
                p.get_units()[0] for p in provider_list]))
        self.session = SessionState(self.unit_list)
        self.desired_job_list = self._get_matching_job_list(
            ns, self.session.job_list)
        self.problem_list = self.session.update_desired_job_list(
            self.desired_job_list)

    def run(self):
        if self.ns.run_local:
            if self.ns.print_desired_job_list:
                self._print_desired_job_list()
            if self.ns.print_run_list:
                self._print_run_list()
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
        if self.ns.print_requirement_report:
            self._print_requirement_report()
        if self.ns.print_desired_job_list:
            self._print_desired_job_list()
        if self.ns.print_run_list:
            self._print_run_list()

    def _print_desired_job_list(self):
        print(_("[Desired Job List]").center(80, '='))
        for job in self.session.desired_job_list:
            print("{}".format(job.id))

    def _print_run_list(self):
        print(_("[Run List]").center(80, '='))
        for job in self.session.run_list:
            print("{}".format(job.id))

    def _run_local_jobs(self):
        print(_("[Running Local Jobs]").center(80, '='))
        manager = SessionManager.create_with_state(self.session)
        try:
            manager.state.metadata.title = "plainbox dev analyze session"
            manager.state.metadata.flags = [SessionMetaData.FLAG_INCOMPLETE]
            manager.checkpoint()
            runner = JobRunner(
                manager.storage.location, self.provider_list,
                os.path.join(manager.storage.location, 'io-logs'),
                command_io_delegate=self)
            again = True
            while again:
                for job in self.session.run_list:
                    if job.plugin == 'local':
                        if self.session.job_state_map[job.id].result.outcome is None:
                            self._run_local_job(manager, runner, job)
                            break
                else:
                    again = False
            manager.state.metadata.flags = []
            manager.checkpoint()
        finally:
            manager.destroy()

    def _run_local_job(self, manager, runner, job):
        print("{job}".format(job=job.id))
        manager.state.metadata.running_job_name = job.id
        manager.checkpoint()
        result = runner.run_job(job, self.config)
        self.session.update_job_result(job, result)
        new_desired_job_list = self._get_matching_job_list(
            self.ns, self.session.job_list)
        new_problem_list = self.session.update_desired_job_list(
            new_desired_job_list)
        if new_problem_list:
            print(_("Problem list"), new_problem_list)
            self.problem_list.extend(new_problem_list)

    def _print_general_stats(self):
        print(_("[General Statistics]").center(80, '='))
        print(_("Known jobs: {}").format(len(self.session.job_list)))
        print(_("Selected jobs: {}").format(len(self.desired_job_list)))

    def _print_dependency_report(self):
        print(_("[Dependency Report]").center(80, '='))
        if self.problem_list:
            for problem in self.problem_list:
                print(" * {}".format(problem))
        else:
            print(_("Selected jobs have no dependency problems"))

    def _print_interactivity_report(self):
        print(_("[Interactivity Report]").center(80, '='))
        if not self.session.run_list:
            return
        max_job_len = max(len(job.id) for job in self.session.run_list)
        fmt = "{{job:{}}} : {{interactive:11}} : {{duration}}".format(
            max_job_len)
        for job in self.session.run_list:
            print(
                fmt.format(
                    job=job.id,
                    interactive=(
                        _("automatic") if job.automated else _("interactive")),
                    duration=(
                        # TODO: use python-babel to format localized timedelta
                        # in 14.04+ as 12.04 babel API is too limited
                        timedelta(seconds=job.estimated_duration)
                        if job.estimated_duration is not None
                        else _("unknown"))
                )
            )

    def _print_estimated_duration_report(self):
        print(_("[Estimated Duration Report]").center(80, '='))
        print(_("Estimated test duration:"))
        automated, manual = self.session.get_estimated_duration()
        print("   " + _("automated tests: {}").format(
            timedelta(seconds=automated) if automated is not None
            else _("cannot estimate")))
        print("   " + _("manual tests: {}").format(
            timedelta(seconds=manual) if manual is not None
            else _("cannot estimate")))
        print("   " + _("total: {}").format(
            timedelta(seconds=manual + automated)
            if manual is not None and automated is not None
            else _("cannot estimate")))

    def _print_validation_report(self, only_errors):
        print(_("[Validation Report]").center(80, '='))
        if not self.session.run_list:
            return
        max_job_len = max(len(job.id) for job in self.session.run_list)
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
            print(fmt.format(job=job.id, problem=problem))
            if problem:
                print(_("Job defined in {}").format(job.origin))
        if only_errors and problem is None:
            print(_("No problems found"))

    def _print_requirement_report(self):
        print(_("[Requirement Report]").center(80, '='))
        if not self.session.run_list:
            return
        requirements = set()
        for job in self.session.run_list:
            if job.requires:
                resource_program = job.get_resource_program()
                if 'package' in resource_program.required_resources:
                    for packages in [
                            resource.text for resource in
                            resource_program.expression_list
                            if resource.resource_id == 'package']:
                        node = ast.parse(packages)
                        visitor = RequirementNodeVisitor()
                        visitor.visit(node)
                        requirements.add((' | ').join(visitor.packages_seen))
        if requirements:
            print(',\n'.join(sorted(requirements)))


class AnalyzeCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Implementation of ``$ plainbox dev analyze``
    """

    def __init__(self, provider_list, config):
        self.provider_list = provider_list
        self.config = config

    def invoked(self, ns):
        return AnalyzeInvocation(self.provider_list, self.config, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "analyze", help=_("analyze how selected jobs would be executed"))
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '-l', '--run-local',
            action='store_true', dest='run_local',
            help=_('run all selected local jobs, required to see true data'))
        group.add_argument(
            '-L', '--skip-local',
            action='store_false', dest='run_local',
            # TRANSLATORS: please keep the word 'local' untranslated.
            # It designates special type of jobs, not their location.
            help=_('do not run local jobs'))
        group = parser.add_argument_group("reports")
        group.add_argument(
            '-s', '--print-stats', action='store_true',
            help=_("print general job statistics"))
        group.add_argument(
            "-d", "--print-dependency-report", action='store_true',
            help=_("print dependency report"))
        group.add_argument(
            "-t", "--print-interactivity-report", action='store_true',
            help=_("print interactivity report"))
        group.add_argument(
            "-e", "--print-estimated-duration-report", action='store_true',
            help=_("print estimated duration report"))
        group.add_argument(
            "-v", "--print-validation-report", action='store_true',
            help=_("print validation report"))
        group.add_argument(
            "-r", "--print-requirement-report", action='store_true',
            help=_("print requirement report"))
        group.add_argument(
            "-E", "--only-errors", action='store_true', default=False,
            help=_(
                "when coupled with -v, only problematic jobs will be listed"))
        group.add_argument(
            "-S", "--print-desired-job-list", action='store_true',
            help=_("print desired job list"))
        group.add_argument(
            "-R", "--print-run-list", action='store_true',
            help=_("print run list"))
        parser.set_defaults(command=self)
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
