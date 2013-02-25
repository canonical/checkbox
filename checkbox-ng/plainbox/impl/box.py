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
plainbox.impl.box
=================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

from argparse import ArgumentParser
from argparse import FileType
from argparse import _ as argparse_gettext
from logging import basicConfig
from logging import getLogger
from os.path import join
import argparse
import re
import sys

from plainbox import __version__ as version
from plainbox.impl.checkbox import CheckBox
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.selftest import SelfTestCommand
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.result import JobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import slugify
from plainbox.impl.session import SessionState


logger = getLogger("plainbox.box")


class CheckBoxCommandMixIn:
    """
    Mix-in class for plainbox commands that want to discover and load checkbox
    jobs
    """
    def __init__(self, checkbox):
        self._checkbox = checkbox

    @property
    def checkbox(self):
        return self._checkbox

    def enhance_parser(self, parser):
        """
        Add common options for job selection to an existing parser
        """
        group = parser.add_argument_group(title="job definition options")
        group.add_argument(
            '-i', '--include-pattern', action="append",
            metavar='PATTERN', default=[], dest='include_pattern_list',
            help="Run jobs matching the given pattern")
        group.add_argument(
            '-x', '--exclude-pattern', action="append",
            metavar="PATTERN", default=[], dest='exclude_pattern_list',
            help="Do not run jobs matching the given pattern")
        # TODO: Find a way to handle the encoding of the file
        group.add_argument(
            '-W', '--whitelist',
            metavar="WHITELIST",
            type=FileType("rt"),
            help="Load whitelist containing run patterns")

    def get_job_list(self, ns):
        """
        Load and return a list of JobDefinition instances
        """
        return self._checkbox.get_builtin_jobs()

    def _get_matching_job_list(self, ns, job_list):
        # Find jobs that matched patterns
        matching_job_list = []
        # Pre-seed the include pattern list with data read from
        # the whitelist file.
        if ns.whitelist:
            ns.include_pattern_list.extend([
                pattern.strip()
                for pattern in ns.whitelist.readlines()])
        # Decide which of the known jobs to include
        for job in job_list:
            # Reject all jobs that match any of the exclude
            # patterns
            for pattern in ns.exclude_pattern_list:
                if re.match(pattern, job.name):
                    break
            else:
                # Then accept (include) all job that matches
                # any of include patterns
                for pattern in ns.include_pattern_list:
                    if re.match(pattern, job.name):
                        matching_job_list.append(job)
                        break
        return matching_job_list


class SpecialCommand(PlainBoxCommand, CheckBoxCommandMixIn):

    def invoked(self, ns):
        job_list = self.get_job_list(ns)
        # Now either do a special action or run the jobs
        if ns.special == "list-jobs":
            self._print_job_list(ns, job_list)
        elif ns.special == "list-expr":
            self._print_expression_list(ns, job_list)
        elif ns.special == "dep-graph":
            self._print_dot_graph(ns, job_list)
        # Always succeed
        return 0

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "special", help="special/internal commands")
        parser.set_defaults(command=self)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-j', '--list-jobs',
            help="List jobs instead of running them",
            action="store_const", const="list-jobs", dest="special")
        group.add_argument(
            '-e', '--list-expressions',
            help="List all unique resource expressions",
            action="store_const", const="list-expr", dest="special")
        group.add_argument(
            '-d', '--dot',
            help="Print a graph of jobs instead of running them",
            action="store_const", const="dep-graph", dest="special")
        parser.add_argument(
            '--dot-resources',
            help="Render resource relationships (for --dot)",
            action='store_true')
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)

    def _get_matching_job_list(self, ns, job_list):
        matching_job_list = super(
            SpecialCommand, self)._get_matching_job_list(ns, job_list)
        # As a special exception, when ns.special is set and we're either
        # listing jobs or job dependencies then when no run pattern was
        # specified just operate on the whole set. The ns.special check
        # prevents people starting plainbox from accidentally running _all_
        # jobs without prompting.
        if ns.special is not None and not ns.include_pattern_list:
            matching_job_list = job_list
        return matching_job_list

    def _print_job_list(self, ns, job_list):
        matching_job_list = self._get_matching_job_list(ns, job_list)
        for job in matching_job_list:
            print("{}".format(job))

    def _print_expression_list(self, ns, job_list):
        matching_job_list = self._get_matching_job_list(ns, job_list)
        expressions = set()
        for job in matching_job_list:
            prog = job.get_resource_program()
            if prog is not None:
                for expression in prog.expression_list:
                    expressions.add(expression.text)
        for expression in sorted(expressions):
            print(expression)

    def _print_dot_graph(self, ns, job_list):
        matching_job_list = self._get_matching_job_list(ns, job_list)
        print('digraph dependency_graph {')
        print('\tnode [shape=box];')
        for job in matching_job_list:
            if job.plugin == "resource":
                print('\t"{}" [shape=ellipse,color=blue];'.format(job.name))
            elif job.plugin == "attachment":
                print('\t"{}" [color=green];'.format(job.name))
            elif job.plugin == "local":
                print('\t"{}" [shape=invtriangle,color=red];'.format(
                    job.name))
            elif job.plugin == "shell":
                print('\t"{}" [];'.format(job.name))
            elif job.plugin in ("manual", "user-verify", "user-interact"):
                print('\t"{}" [color=orange];'.format(job.name))
            for dep_name in job.get_direct_dependencies():
                print('\t"{}" -> "{}";'.format(job.name, dep_name))
            prog = job.get_resource_program()
            if ns.dot_resources and prog is not None:
                for expression in prog.expression_list:
                    print('\t"{}" [shape=ellipse,color=blue];'.format(
                        expression.resource_name))
                    print('\t"{}" -> "{}" [style=dashed, label="{}"];'.format(
                        job.name, expression.resource_name,
                        expression.text.replace('"', "'")))
        print("}")


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
            metavar='FILE', type=FileType("wt"),
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
        session = SessionState(job_list)
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
        if ns.output_file is sys.stdout:
            print("[ Results ]".center(80, '='))
        else:
            print("Saving results to {}".format(ns.output_file.name))
        data = exporter.get_session_data_subset(session)
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
                'outcome': JobResult.OUTCOME_NOT_SUPPORTED
            })
        if job_result is None and not ns.dry_run:
            logger.warning("Job %s did not return a result", job)
        if job_result is not None:
            session.update_job_result(job, job_result)


class PlainBox:
    """
    High-level plainbox object
    """

    def __init__(self):
        self._checkbox = CheckBox()

    def main(self, argv=None):
        # TODO: setup sane logging system that works just as well for Joe user
        # that runs checkbox from the CD as well as for checkbox developers and
        # custom debugging needs.  It would be perfect^Hdesirable not to create
        # another broken, never-rotated, uncapped logging crap that kills my
        # SSD by writing junk to ~/.cache/
        basicConfig(level="WARNING")
        parser = self._construct_parser()
        ns = parser.parse_args(argv)
        # Set the desired log level
        getLogger("").setLevel(ns.log_level)
        # Argh the horrror!
        #
        # Since CPython revision cab204a79e09 (landed for python3.3)
        # http://hg.python.org/cpython/diff/cab204a79e09/Lib/argparse.py
        # the argparse module behaves differently than it did in python3.2
        #
        # In practical terms subparsers are now optional in 3.3 so all of the
        # commands are no longer required parameters.
        #
        # To compensate, on python3.3 and beyond, when the user just runs
        # plainbox without specifying the command, we manually, explicitly do
        # what python3.2 did: call parser.error(_('too few arguments'))
        if (sys.version_info[:2] >= (3, 3)
                and getattr(ns, "command", None) is None):
            parser.error(argparse_gettext("too few arguments"))
        else:
            return ns.command.invoked(ns)

    def _construct_parser(self):
        parser = ArgumentParser(prog="plainbox")
        parser.add_argument(
            "-v", "--version", action="version",
            version="{}.{}.{}".format(*version[:3]))
        parser.add_argument(
            "-l", "--log-level", action="store",
            choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
            default='WARNING',
            help=argparse.SUPPRESS)
        subparsers = parser.add_subparsers()
        RunCommand(self._checkbox).register_parser(subparsers)
        SpecialCommand(self._checkbox).register_parser(subparsers)
        SelfTestCommand().register_parser(subparsers)
        #group = parser.add_argument_group(title="user interface options")
        #group.add_argument(
        #    "-u", "--ui", action="store",
        #    default=None, choices=('headless', 'text', 'graphics'),
        #    help="select the UI front-end (defaults to auto)")
        return parser


def main(argv=None):
    # Instantiate a global plainbox instance
    # XXX: Allow one to control the checkbox= argument via
    # environment or config.
    box = PlainBox()
    retval = box.main(argv)
    raise SystemExit(retval)


def get_builtin_jobs():
    raise NotImplementedError("get_builtin_jobs() not implemented")


def save(something, somewhere):
    raise NotImplementedError("save() not implemented")


def run(*args, **kwargs):
    raise NotImplementedError("run() not implemented")
