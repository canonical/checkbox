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
from fnmatch import fnmatch
from io import TextIOWrapper
from logging import basicConfig
from logging import getLogger
from os import listdir
from os.path import join

from plainbox import __version__ as version
from plainbox.impl.checkbox import CheckBox
from plainbox.impl.job import JobDefinition
from plainbox.impl.resource import ResourceContext
from plainbox.impl.rfc822 import load_rfc822_records
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import Scratch
from plainbox.impl.depmgr import DependencyError
from plainbox.impl.depmgr import DependencySolver


logger = getLogger("plainbox.box")


class PlainBox:
    """
    High-level plainbox object
    """

    def __init__(self):
        self._checkbox = CheckBox()
        self._context = ResourceContext()
        self._scratch = Scratch()
        self._runner = JobRunner(self._checkbox, self._context, self._scratch)

    def main(self, argv=None):
        basicConfig(level="WARNING")
        # TODO: setup sane logging system that works just as well for Joe user
        # that runs checkbox from the CD as well as for checkbox developers and
        # custom debugging needs.  It would be perfect^Hdesirable not to create
        # another broken, never-rotated, uncapped logging crap that kills my
        # SSD by writing junk to ~/.cache/
        parser = ArgumentParser(prog="plainbox")
        parser.add_argument(
            "-v", "--version", action="version",
            version="{}.{}.{}".format(*version[:3]))
        parser.add_argument(
            "-l", "--log-level", action="store",
            choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
            help="Set logging level")
        group = parser.add_argument_group(title="user interface options")
        group.add_argument(
            "-u", "--ui", action="store",
            default=None, choices=('headless', 'text', 'graphics'),
            help="select the UI front-end (defaults to auto)")
        group = parser.add_argument_group(title="job definition options")
        group.add_argument(
            "--load-extra", action="append",
            metavar="FILE", default=[],
            help="Load extra job definitions from FILE",
            type=FileType("rt"))
        group.add_argument(
            '-r', '--run-pattern', action="append",
            metavar='PATTERN', default=[], dest='run_pattern_list',
            help="Run jobs matching the given pattern")
        group.add_argument(
            '-n', '--dry-run', action='store_true',
            help="Don't actually run any jobs")
        group = parser.add_argument_group("special options")
        group.add_argument(
            '--list-jobs', help="List jobs instead of running them",
            action="store_const", const="list-jobs", dest="special")
        group.add_argument(
            '--list-expressions', help="List all unique resource expressions",
            action="store_const", const="list-expr", dest="special")
        group.add_argument(
            '--dot', help="Print a graph of jobs instead of running them",
            action="store_const", const="dep-graph", dest="special")
        group.add_argument(
            '--dot-resources', action='store_true',
            help="Render resource relationships (for --dot)")
        ns = parser.parse_args(argv)
        # Set the desired log level
        if ns.log_level:
            getLogger("").setLevel(ns.log_level)
        # Load built-in job definitions
        job_list = self.get_builtin_jobs()
        # Load additional job definitions
        job_list.extend(self._load_jobs(ns.load_extra))
        # Find jobs that matched patterns
        matching_job_list = []
        for job in job_list:
            for pattern in ns.run_pattern_list:
                if fnmatch(job.name, pattern):
                    matching_job_list.append(job)
                    break
        # As a special exception, when ns.special is set and we're either
        # listing jobs or job dependencies then when no run pattern was
        # specified just operate on the whole set. The ns.special check
        # prevents people starting plainbox from accidentally running _all_
        # jobs without prompting.
        if ns.special is not None and not ns.run_pattern_list:
            matching_job_list = job_list
        # Now either do a special action or run the jobs
        if ns.special == "list-jobs":
            self._print_job_list(ns, matching_job_list)
        elif ns.special == "list-expr":
            self._print_expression_list(ns, matching_job_list)
        elif ns.special == "dep-graph":
            self._print_dot_graph(ns, matching_job_list)
        else:
            # And run them
            with self._scratch:  # TODO: Promote to a persistent session object
                return self.run(job_list, matching_job_list, ns.dry_run)

    def _print_job_list(self, ns, matching_job_list):
        for job in matching_job_list:
            print("{}".format(job))

    def _print_expression_list(self, ns, matching_job_list):
        expressions = set()
        for job in matching_job_list:
            prog = job.get_resource_program()
            if prog is not None:
                for expression in prog.expression_list:
                    expressions.add(expression.text)
        for expression in sorted(expressions):
            print(expression)

    def _print_dot_graph(self, ns, matching_job_list):
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

    def run(self, job_list, matching_job_list, dry_run):
        # Compute required resources
        print("[ Analyzing Jobs ]".center(80, '='))
        try:
            sorted_job_list = DependencySolver.resolve_dependencies(
                job_list, matching_job_list)
        except DependencyError as exc:
            print("Problem wit job {}: {}".format(exc.affected_job, exc))
            return
        else:
            resource_job_list = [job for job in sorted_job_list
                                 if job.plugin == "resource"]
            other_job_list = [job for job in sorted_job_list
                              if job.plugin != "resource"]
        print("[ Gathering Resources ]".center(80, '='))
        if not resource_job_list:
            print("No resource jobs required")
        else:
            self._run_jobs(resource_job_list, dry_run)
        # Run non-resource jobs
        result_list = []
        print("[ Testing ]".center(80, '='))
        if not other_job_list:
            print("No jobs selected")
        else:
            result_list = self._run_jobs(other_job_list, dry_run)
            print("[ Results ]".center(80, '='))
            for result in result_list:
                print(" * {}: {}".format(
                    result.job.name, result.outcome))

    def get_builtin_jobs(self):
        logger.debug("Loading built-in jobs...")
        return self._load_builtin_jobs()

    def save(self, something, somewhere):
        raise NotImplementedError()

    def load(self, somewhere):
        if isinstance(somewhere, str):
            # Load data from a file with the given name
            filename = somewhere
            with open(filename, 'rt', encoding='UTF-8') as stream:
                return load(stream)
        if isinstance(somewhere, TextIOWrapper):
            stream = somewhere
            logger.debug("Loading jobs definitions from %r...", stream.name)
            record_list = load_rfc822_records(stream)
            job_list = []
            for record in record_list:
                job = JobDefinition.from_rfc822_record(record)
                logger.debug("Loaded %r", job)
                job_list.append(job)
            return job_list
        else:
            raise TypeError(
                "Unsupported type of 'somewhere': {!r}".format(
                    type(somewhere)))

    def _run_jobs(self, job_list, dry_run):
        result_list = []
        for job in job_list:
            print("[ {} ]".format(job.name).center(80, '-'))
            print()
            if job.description:
                print(job.description)
            else:
                print("This job has no description")
            print()
            print("This job has the following attributes set: {}".format(
                ", ".join((attr for attr in job._data))))
            print("This job uses plugin: {}".format(job.plugin))
            if job.command:
                print("This job uses the following bash command: {!r}".format(
                    job.command))
            if job.depends is not None:
                print("This job depends on the following jobs:")
                for job_name in job.get_direct_dependencies():
                    print(" - {}".format(job_name))
            prog = job.get_resource_program()
            if prog:
                print("This job depends on the following expressions:")
                for expression in prog.expression_list:
                    print(" - {}".format(expression.text))
                if dry_run:
                    print("Assuming the expressions would match")
                else:
                    met = prog.evaluate(self._context.resources)
                    if met:
                        print("Job requirements met")
                    else:
                        print("Job requirements NOT met")
                        return
            try:
                print("Starting job... ", end="")
                if dry_run:
                    print("(not really running anything) ", end="")
                    result = None
                else:
                    result = self._runner.run_job(job)
            except NotImplementedError:
                print("error")
                logger.exception("Something was not implemented fully")
            else:
                print("done")
                if result is not None:
                    result_list.append(result)
                elif job.plugin == "resource":
                    pass
                else:
                    if not dry_run:
                        logger.warning("Job %s did not return a result", job)
        return result_list

    def _load_jobs(self, source_list):
        """
        Load jobs from the list of sources
        """
        job_list = []
        for source in source_list:
            job_list.extend(self.load(source))
        return job_list

    def _load_builtin_jobs(self):
        """
        Load jobs from built into CheckBox
        """
        return self._load_jobs([
            join(self._checkbox.jobs_dir, name)
            for name in listdir(self._checkbox.jobs_dir)
            if name.endswith(".txt") or name.endswith(".txt.in")])


# Instantiate a global plainbox instance
# XXX: Allow one to control the checkbox= argument via environment or config.
box = PlainBox()

# Extract the methods from the global instance, needed by the public API
get_builtin_jobs = box.get_builtin_jobs
save = box.save
load = box.load
run = box.run
main = box.main
