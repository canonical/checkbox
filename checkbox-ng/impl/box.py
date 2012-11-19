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
            metavar='PATTERN', default=[],
            help="Run jobs matching the given pattern")
        group.add_argument(
            '--list-jobs', help="List all jobs",
            action="store_true")
        ns = parser.parse_args(argv)
        # Set the desired log level
        if ns.log_level:
            getLogger("").setLevel(ns.log_level)
        # Load built-in job definitions
        job_list = self.get_builtin_jobs()
        # Load additional job definitions
        job_list.extend(self._load_jobs(ns.load_extra))
        if ns.list_jobs:
            print("Available jobs:")
            for job in job_list:
                print(" - {}".format(job))
        else:
            # And run them
            with self._scratch:
                return self.run(
                    run_pattern_list=ns.run_pattern,
                    job_list=job_list,
                    ui=ns.ui)

    def run(self, run_pattern_list, job_list, **kwargs):
        job_map = {job.name: job for job in job_list}
        matching_job_list = []
        # Find jobs that matched patterns
        print("[ Searching for Matching Jobs ]".center(80, '='))
        for job in job_list:
            for pattern in run_pattern_list:
                if fnmatch(job.name, pattern):
                    matching_job_list.append(job)
                    break
        print("Matching jobs: {}".format(
            ', '.join((job.name for job in matching_job_list))))
        # Compute required resources
        print("[ Analyzing Jobs ]".center(80, '='))
        needed_resource_jobs = set()
        resource_job_list = []
        for job in matching_job_list:
            prog = job.get_resource_program()
            if prog is None:
                continue
            for resource_name in prog.required_resources:
                if resource_name in needed_resource_jobs:
                    continue
                else:
                    needed_resource_jobs.add(resource_name)
                try:
                    required_job = job_map[resource_name]
                except KeyError:
                    print("Unable to find resource {!r} required by job"
                          " {}".format(resource_name, job))
                    print("Job {} will not run".format(job))
                    matching_job_list.remove(job)
                if required_job.plugin != "resource":
                    print("Job {} references resource {!r} but job {} uses"
                          " non-resource plugin {!r}".format(
                              job, resource_name, required_job,
                              required_job.plugin))
                    print("Job {} will not run".format(job))
                    matching_job_list.remove(job)
                else:
                    resource_job_list.append(required_job)
        # Resolve dependencies in resource jobs
        # XXX: not implemented
        print("Required resource jobs: {}".format(
            ', '.join((job.name for job in resource_job_list))))
        # Run resource jobs
        print("[ Gathering Resources ]".center(80, '='))
        if not resource_job_list:
            print("No resource jobs required")
        else:
            self._run_jobs(resource_job_list)
        # Run non-resource jobs
        result_list = []
        other_job_list = [
            job
            for job in matching_job_list
            if job.plugin != "resource"]
        print("[ Testing ]".center(80, '='))
        if not other_job_list:
            print("No jobs selected")
        else:
            result_list = self._run_jobs(other_job_list)
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

    def _run_jobs(self, job_list):
        result_list = []
        for job in job_list:
            print("[ {} ]".format(job.name).center(80, '-'))
            if job.description:
                print()
                print(job.description.center(80))
                print()
                print("_" * 80)
            print(" * job attributes set: {}".format(
                ", ".join((attr for attr in job._data))))
            print(" * job type: {}".format(job.plugin))
            if job.command:
                print(" * job command: {!r}".format(job.command))
            if job.depends is not None:
                print(" * job dependencies: {}".format(', '.join(job.depends)))
            prog = job.get_resource_program()
            if prog:
                met = prog.evaluate(self._context.resources)
                print(" * job requirements: {}".format(
                    "met" if met else "not met"))
                for expression in prog.expression_list:
                    print("   - {}".format(expression.text))
            try:
                print(" * starting job... ", end="")
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
