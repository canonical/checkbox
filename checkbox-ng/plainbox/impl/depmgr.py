# This file is part of Checkbox.
#
# Copyright 2012-2025 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
Job Dependency Solver.


:mod:`plainbox.impl.depmgr`
===========================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from abc import ABCMeta
from abc import abstractproperty
from logging import getLogger
import enum

from plainbox.i18n import gettext as _
from plainbox.impl.job import JobDefinition

logger = getLogger("plainbox.depmgr")


class DependencyType(enum.Enum):
    """
    The types of dependencies that can be expressed in the system.
    - resource:
       ...
    - depends:
        ...
    - after:
        ...
    - before:
        ...
    """

    RESOURCE = "resource"
    DEPENDS = "depends"
    AFTER = "after"
    BEFORE = "before"


class DependencyError(Exception, metaclass=ABCMeta):
    """Exception raised when a dependency error is detected."""

    @abstractproperty
    def affected_job(self):
        """job that is affected by the dependency error."""

    @abstractproperty
    def affecting_job(self):
        """
        job that is affecting the :attr:`affected_job`.

        This may be None in certain cases (eg, when the job does not exist and
        is merely referred to by id). If this job exists removing it SHOULD
        fix this problem from occurring.

        This may be the same as :attr:`affected_job`
        """


class DependencyUnknownError(DependencyError):
    """
    Exception raised when an unknown job is mentioned.

    .. note::
        This class differs from :class:`DependencyMissingError` in that the
        unknown job is not a dependency of anything. It can only happen when
        the job is explicitly mentioned in the list of jobs to visit.
    """

    def __init__(self, job):
        """Initialize a new DependencyUnknownError with a given job."""
        self.job = job

    @property
    def affected_job(self):
        """
        job that is affected by the dependency error.

        Here it's a job that on the ``visit_list`` but not on the ``job_list``.
        """
        return self.job

    @property
    def affecting_job(self):
        """
        job that is affecting the :attr:`affected_job`.

        Here, it is always None.
        """

    def __str__(self):
        """Get a printable description of an error."""
        return _("unknown job referenced: {!a}").format(self.job.id)

    def __repr__(self):
        """Get a debugging representation of an error."""
        return "<{} job:{!r}>".format(self.__class__.__name__, self.job)

    def __eq__(self, other):
        """Check if one error is equal to another."""
        if not isinstance(other, DependencyUnknownError):
            return NotImplemented
        return self.job == other.job

    def __hash__(self):
        """Calculate the hash of an error."""
        return hash((self.job,))


class DependencyCycleError(DependencyError):
    """Exception raised when a cyclic dependency is detected."""

    def __init__(self, job_list):
        """
        Initialize with a list of jobs that form a dependency loop.

        The dependencies satisfy the given expression:

            job_list[n - 1] depends-on job_list[n]

        The error exists because job_list[0] is job_list[-1].
        Each item is a JobDefinition instance.
        """
        assert len(job_list) > 1
        assert job_list[0] is job_list[-1]
        self.job_list = job_list

    @property
    def affected_job(self):
        """
        job that is affected by the dependency error.

        Here it is the job that has a cyclic dependency on itself.
        """
        return self.job_list[0]

    @property
    def affecting_job(self):
        """
        job that is affecting the :attr:`affected_job`.

        Here it's always the same as :attr:`~DependencyCycleError.affected_job`
        """
        return self.affected_job

    def __str__(self):
        """Get a printable description of an error."""
        return _("dependency cycle detected: {}").format(
            " -> ".join([job.id for job in self.job_list])
        )

    def __repr__(self):
        """Get a debugging representation of an error."""
        return "<{} job_list:{!r}>".format(
            self.__class__.__name__, self.job_list
        )


class DependencyMissingError(DependencyError):
    """Exception raised when a job has an unsatisfied dependency."""

    def __init__(self, job, missing_job_id, dep_type):
        """Initialize a new error with given data."""
        self.job = job
        self.missing_job_id = missing_job_id

        if not isinstance(dep_type, DependencyType):
            raise TypeError("Invalid dependency type: {!r}".format(dep_type))
        self.dep_type = dep_type.value

    @property
    def affected_job(self):
        """
        job that is affected by the dependency error.

        Here it is the job that has a missing dependency.
        """
        return self.job

    @property
    def affecting_job(self):
        """
        job that is affecting the :attr:`affected_job`.

        Here it is always None as we have not seen this job at all and that's
        what's causing the problem in the first place.
        """

    def __str__(self):
        """Get a printable description of an error."""
        return _("missing dependency: {!r} ({})").format(
            self.missing_job_id, self.dep_type
        )

    def __repr__(self):
        """Get a debugging representation of an error."""
        return "<{} job:{!r} missing_job_id:{!r} dep_type:{!r}>".format(
            self.__class__.__name__,
            self.job,
            self.missing_job_id,
            self.dep_type,
        )

    def __eq__(self, other):
        """Check if one error is equal to another."""
        if not isinstance(other, DependencyMissingError):
            return NotImplemented
        return (
            self.job == other.job
            and self.missing_job_id == other.missing_job_id
            and self.dep_type == other.dep_type
        )

    def __hash__(self):
        """Calculate the hash of an error."""
        return hash((self.job, self.missing_job_id, self.dep_type))


class DependencyDuplicateError(DependencyError):
    """Exception raised when two jobs have the same id."""

    def __init__(self, job, duplicate_job):
        """Initialize a new error with given data."""
        assert job.id == duplicate_job.id
        self.job = job
        self.duplicate_job = duplicate_job

    @property
    def affected_job(self):
        """
        job that is affected by the dependency error.

        Here it is the job that is already known by the system.
        """
        return self.job

    @property
    def affecting_job(self):
        """
        job that is affecting the :attr:`affected_job`.

        Here it is the job that is clashing with another job already present in
        the system.
        """
        return self.duplicate_job

    def __str__(self):
        """Get a printable description of an error."""
        return _("duplicate job id: {!r}").format(self.affected_job.id)

    def __repr__(self):
        """Get a debugging representation of an error."""
        return "<{} job:{!r} duplicate_job:{!r}>".format(
            self.__class__.__name__, self.job, self.duplicate_job
        )


class Group(object):
    def __init__(self, name, jobs=None, external_deps=None):
        self.name = name
        self.jobs = [] if jobs is None else list(jobs)
        self.external_deps = (
            [] if external_deps is None else set(external_deps)
        )


class State(enum.Enum):
    """
    States for recursive DFS graph visitor.

    NOT_VISITED:
        For nodes have not been visited yet.
    VISITED:
        For nodes that are currently being visited but the visit is not
        finished.
    FINISHED:
        For nodes that have been visited and are finished.
    """

    NOT_VISITED = "not_visited"
    VISITED = "visited"
    FINISHED = "finished"


class DependencySolver:
    """
    Dependency solver for Jobs.

    Uses a simple depth-first search to discover the sequence of jobs should
    be run. The algorithm will detect cycles and will also order all the jobs
    according to their dependencies.
    https://en.wikipedia.org/wiki/Cycle_%28graph_theory%29?#Algorithm
    Use the resolve_dependencies() class method to get the solution.
    """

    GROUP_PREFIX = "_group_job_"

    @classmethod
    def resolve_dependencies(cls, job_list, visit_list=None):
        """
        Solve the dependency graph expressed as a list of job definitions.

        :param list job_list: list of known jobs
        :param list visit_list: (optional) list of jobs to solve

        The visit_list, if specified, allows to consider only a part of the
        graph while still having access and knowledge of all jobs.

        :returns list: the solution (a list of jobs to execute in order)
        :raises DependencyDuplicateError:
            if a duplicate job definition is present
        :raises DependencyCycleError:
            if a cyclic dependency is present.
        :raises DependencyMissingError:
            if a required job does not exist.
        """
        return cls(job_list)._solve(visit_list)

    def __init__(self, job_list):
        """
        Instantiate a new dependency solver with the specified list of jobs.

        :raises DependencyDuplicateError:
            if the initial job_list has any duplicate jobs
        """
        # Remember the jobs that were passed
        self._job_list = job_list
        # Build a map of jobs (by id)
        self._job_map = self._get_job_map(job_list)

        # Solution for all the dependencies that may pull in new jobs
        self._pull_solution = []
        # Intermediate solution for ordering dependencies
        self._order_solution = []

        # Create some variables to handle grouping
        self._groups = dict()
        self._jobs_in_groups = dict()

        self._job_state_map = {
            job.id: State.NOT_VISITED for job in self._job_list
        }

    def _clear_state_map(self):
        self._job_state_map = {
            k: State.NOT_VISITED for k in self._job_state_map.keys()
        }

    def _solve(self, visit_list=None):
        """
        Internal method of DependencySolver.

        Solves the dependency graph and returns the solution.
        The algorithm runs in two passes:
        1. Pulls all the dependencies of the initial jobs and builds a solution
        2. Orders the jobs in the solution according to their dependencies

        The two passes are required to treat the dependencies that pull in
        new jobs differently from the dependencies that only change the order

        Calls _visit() on each of the initial nodes/jobs
        """
        # Visit the visit list
        logger.debug(_("Starting solve"))
        logger.debug(_("Solver job list: %r"), self._job_list)
        logger.debug(_("Solver visit list: %r"), visit_list)

        # If no visit list is specified, use the full job list
        if visit_list is None:
            self._visit_list = self._job_list
        else:
            self._visit_list = visit_list

        # Solve first for pulling dependencies
        pull_solution = self._solve_pull_deps(self._visit_list)

        # Create a map of pulled jobs
        self._pulled_map = self._get_job_map(pull_solution)
        # Add the before dependencies for the jobs in the map
        for job in pull_solution:
            job.controller.add_before_deps(
                job, self._pulled_map, self._job_map
            )

        # Look for groups in the pulled map
        self.create_groups(pull_solution)

        # If there are no groups declared in the pulled jobs, solve the
        # ordering normally
        if not self._groups:
            final_solution = self._solve_order_deps(pull_solution)

        # If there are any groups, solve for ordering considering them
        else:
            # Replace the jobs in the pulled map with the group job
            replaced_solution = self.replace_jobs_by_groups(pull_solution)

            # Solve again for order dependencies
            general_solution = self._solve_order_deps(
                replaced_solution, group=None
            )

            # Solve internally for each group
            group_solutions = {}
            for group in self._groups.values():
                # Get the jobs in the group from the map of pulled jobs
                name = group.name
                group_jobs = [
                    self._pulled_map[job_id] for job_id in group.jobs
                ]
                group_solutions[name] = self._solve_order_deps(
                    group_jobs, group=name
                )

            # Replace the group jobs with the original jobs inside the group
            final_solution = self.replace_groups_by_jobs(
                general_solution, group_solutions
            )

        # Perform a sanity check to ensure that no jobs have been added or
        # removed from the solution.
        pull_jobs = set(pull_solution)
        order_jobs = set(final_solution)
        if pull_jobs != order_jobs:
            raise ValueError(
                "The dependency manager failed ordering the jobs, some jobs "
                "have changed during the ordering process:\n"
                "Pull solution: {!r}\n"
                "Order solution: {!r}".format(pull_jobs, order_jobs)
            )

        return final_solution

    def _solve_pull_deps(self, visit_list):
        self._clear_state_map()
        self._pull_solution = []
        for job in visit_list:
            self._visit(job, pull=True)

        return self._pull_solution

    def _solve_order_deps(self, visit_list, group=None):
        self._clear_state_map()
        self._order_solution = []
        for job in visit_list:
            self._visit(job, group=group)

        return self._order_solution

    def _visit(self, job, trail=None, pull=False, group=None):
        """
        Internal method of DependencySolver.

        Called each time a node is visited. Nodes already seen in _visited are
        skipped. Attempts to enumerate all dependencies (both direct and
        resource) and resolve them. Missing jobs cause DependencyMissingError
        to be raised. Calls _visit recursively on all dependencies.
        Dependencies are pulled form the search_map only if the pull flag is
        set to True.

        Pseudocode of the algorithm:
        visit(job)
            if state == State.FINISHED
                return
            if state == State.VISITED
                raise DependencyCycleError
            if state == State.NOT_VISITED
                state = State.VISITED
                for dep in job.dependencies
                    visit(dep)
                state = State.FINISHED
                solution.append(job)
        """
        # Perform a sanity check to ensure that we have defined the state of
        # this job.
        try:
            state = self._job_state_map[job.id]
        except KeyError:
            logger.debug(_("Visiting job that's not on the job_list: %r"), job)
            raise DependencyUnknownError(job)

        if state == State.NOT_VISITED:
            # This node has not been visited yet. Let's mark it as visited
            # and iterate through the list of dependencies
            self._job_state_map[job.id] = State.VISITED

            # If the trail was not specified start a trail for this node
            # the trail is only used to report dependency cycles
            if trail is None:
                trail = [job]

            if pull:
                # If this is a pull operation we only care about the
                # dependencies that are resource, depends or after.
                self._pull_visit(job, trail)
            else:
                self._order_visit(job, trail, group=group)

        elif state == State.VISITED:
            # This node is not fully traced yet but has been visited already
            # so we've found a dependency loop. We need to cut the initial
            # part of the trail so that we only report the part that actually
            # forms a loop
            trail = trail[trail.index(job) :]
            logger.debug(_("Found dependency cycle: %r"), trail)
            raise DependencyCycleError(trail)

        elif state == State.FINISHED:
            # This node has been visited and is fully traced.
            # We can just skip it and go back
            return
        else:
            raise ValueError(
                "Invalid state for job {!r}: {!r}".format(job.id, state)
            )

    def _pull_visit(self, job, trail=None):
        # We travel through dependencies recursively
        for dep_type, job_id in job.controller.get_dependency_set(
            job, self._visit_list
        ):
            # If this is a pull operation we only care about the dependencies
            # that are resource, depends or after, since only those can pull
            # new jobs into the solution.
            if dep_type not in (
                DependencyType.RESOURCE,
                DependencyType.DEPENDS,
                # If we get rid of the "pulling" behavior of after deps,
                # we can remove this type.
                DependencyType.AFTER,
            ):
                continue

            # We look up the job in the whole job map
            try:
                next_job = self._job_map[job_id]
            except KeyError:
                logger.info(
                    _("Found missing dependency: %r from %r (%r)"),
                    job_id,
                    job,
                    dep_type.value,
                )
                raise DependencyMissingError(job, job_id, dep_type)

            else:
                # Visit the dependency and update the trail
                logger.debug(_("Visiting dependency: %r"), next_job)
                # Update the trail as we visit that node
                trail.append(next_job)
                self._visit(next_job, trail, pull=True)
                trail.pop()

        # We've visited (recursively) all dependencies of this node, so we
        # can change the state to finished and append it to the solution
        self._job_state_map[job.id] = State.FINISHED
        self._pull_solution.append(job)

    def _order_visit(self, job, trail=None, group=None):
        # We travel through dependencies recursively
        for dep_type, job_id in job.controller.get_dependency_set(
            job, self._pull_solution
        ):
            # Check if we are ordering a group
            if group is None:
                # If the dependency is pointing to a job inside a group, we
                # replace it with the group job.
                if job_id in self._jobs_in_groups:
                    group_name = self._jobs_in_groups[job_id]
                    job_id = "{}{}".format(self.GROUP_PREFIX, group_name)
            else:
                # If we are in a group, we only care about the dependencies
                # inside the group
                if self._jobs_in_groups.get(job_id) != group:
                    continue

            try:
                # We look up the job only in the map of pulled jobs
                next_job = self._pulled_map[job_id]
            except KeyError:
                # Since this is an order operation, we don't care if the dep
                # is not in the list of pulled jobs
                logger.info(
                    _("Found missing dependency: %r from %r (%r)"),
                    job_id,
                    job,
                    dep_type.value,
                )
            else:
                # Visit the dependency and update the trail
                logger.debug(_("Visiting dependency: %r"), next_job)
                trail.append(next_job)
                self._visit(next_job, trail, pull=False, group=group)
                trail.pop()

        # We've visited (recursively) all dependencies of this node, so we
        # can change the state to finished and append it to the solution
        self._job_state_map[job.id] = State.FINISHED
        self._order_solution.append(job)

    def create_groups(self, solution):
        """
        Create the groups that are used in the list of pulled jobs.
        """
        self._groups = {}
        self._jobs_in_groups = {}

        for job in solution:
            if getattr(job, "group", None):
                # Check if the group is already in the map
                name = job.group
                if name not in self._groups:
                    self._groups[name] = Group(name)
                self._groups[name].jobs.append(job.id)
                self._jobs_in_groups[job.id] = name

        for group in self._groups.values():
            group.external_deps = self.get_external_dependencies(group)

    def get_external_dependencies(self, group):
        """
        Get the external dependencies for the groups.
        The external dependencies are the dependencies of the jobs inside the
        group that don't point to the jobs inside the group
        """
        external_deps = set()
        for job_id in group.jobs:
            # Get the dependencies for the job
            job = self._pulled_map[job_id]
            deps = job.controller.get_dependency_set(job, self._pulled_map)
            # Filter out the dependencies that are not external
            for dep_type, job_id in deps:
                if self._jobs_in_groups.get(job_id) != group.name:
                    external_deps.add(job_id)
        return external_deps

    def replace_jobs_by_groups(self, solution):
        """
        Replace the jobs in the pulled map with the group jobs.
        """
        added_groups = set()

        def replace_iter():
            for job in solution:
                group_name = self._jobs_in_groups.get(job.id)

                # Not in any group: continue
                if group_name is None:
                    yield job
                    continue

                # Already in a group: skip
                if group_name in added_groups:
                    continue

                # Create the group job
                group_job_id = f"{self.GROUP_PREFIX}{group_name}"
                # Add external dependencies as dependencies of the group job
                deps = self._groups[group_name].external_deps
                group_job = JobDefinition(
                    {"id": group_job_id, "after": " ".join(deps)}
                )

                # Add the group job to the pulled map and job state map
                self._pulled_map[group_job_id] = group_job
                self._job_state_map[group_job_id] = State.NOT_VISITED

                added_groups.add(group_name)
                yield group_job

        return list(replace_iter())

    def replace_groups_by_jobs(self, solution, group_solutions):
        """
        Replace the temporary group jobs with the original jobs inside the
        group.
        """

        def replace_iter():
            for job in solution:
                if job.id.startswith(self.GROUP_PREFIX):
                    # Remove the prefix and get the group name
                    name = job.id.split(self.GROUP_PREFIX)[1]
                    # Add the jobs from the group
                    yield from group_solutions.get(name, [job])
                else:
                    yield job

        return list(replace_iter())

    @staticmethod
    def _get_job_map(job_list):
        """
        Internal method of DependencySolver.

        Computes a map of job.id => job
        Raises DependencyDuplicateError if a collision is found
        """
        job_map = {}
        for job in job_list:
            if job.id in job_map:
                raise DependencyDuplicateError(job_map[job.id], job)
            else:
                job_map[job.id] = job
        return job_map
