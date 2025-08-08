# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
        :raises DependencyMissingErorr:
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
        # The computed solution for all dependencies
        self._final_solution = []

        # Create some variables to handle grouping
        self._groups = dict()
        self._jobs_in_groups = dict()
        self._current_group = None
        self._group_solutions = dict()

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
        self._clear_state_map()
        for job in self._visit_list:
            self._visit(job, pull=True)

        # Create a map of pulled jobs
        self._pulled_map = self._get_job_map(self._pull_solution)
        # Add the before dependencies for the jobs in the map
        for job in self._pull_solution:
            job.controller.add_before_deps(
                job, self._pulled_map, self._job_map
            )
        self._clear_state_map()

        self.create_groups()
        # Print the groups
        if self._groups:
            print(
                "--->Groups referenced in pulled jobs: {}".format(self._groups)
            )

        # Replace the jobs in the pulled map with the group job
        group_solution = self.replace_jobs_by_groups(self._pull_solution)
        print("Pulled map after group replacement: {}".format(group_solution))

        # Solve again for order dependencies, using the pulled jobs as the
        # new visit list
        self._clear_state_map()
        self._order_solution = []
        for job in self._pull_solution:
            self._visit(job)
        group_solution = self._order_solution

        # Solve internally for each group
        for group, jobs in self._groups.items():
            self._order_solution = []
            self._clear_state_map()
            jobs = [self._pulled_map[job_id] for job_id in jobs]
            self._current_group = group
            for job in jobs:
                self._visit(job)

            print(
                "******Group {} solution: {}".format(
                    group, self._order_solution
                )
            )

            self._group_solutions[group] = self._order_solution

        self._final_solution = self.replace_groups_by_jobs(group_solution)
        print(
            "Order solution after group replacement: {}".format(
                self._order_solution
            )
        )

        # Perform a sanity check to ensure that no jobs have been added or
        # removed from the solution.
        pull_jobs = set(self._pull_solution)
        order_jobs = set(self._final_solution)
        if pull_jobs != order_jobs:
            raise ValueError(
                "The dependency manager failed ordering the jobs, some jobs "
                "have changed during the ordering process:\n"
                "Pull solution: {!r}\n"
                "Order solution: {!r}".format(pull_jobs, order_jobs)
            )

        print("********Done solving**********")

        # Return the final solution
        return self._final_solution

    def _visit(self, job, trail=None, pull=False):
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
            # logger.debug(_("Visiting job that's not on the job_list: %r"), job)
            for job in self._job_state_map:
                print(job)
            print(_("Visiting job that's not on the job_list: %r"), job)
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
                # If this is an order operation we only care about the
                # dependencies that are depends or before.
                self._order_visit(job, trail)

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

    def _order_visit(self, job, trail=None):
        # We travel through dependencies recursively
        # print(" - Checking order visit for job: {}".format(job.id))
        for dep_type, job_id in job.controller.get_dependency_set(
            job, self._pull_solution
        ):

            if self._current_group is None:
                # If the dependency is pointing to a job inside a group, we
                # replace it with the group job.
                if job_id in self._jobs_in_groups:
                    group_name = self._jobs_in_groups[job_id]
                    job_id = "{}{}".format(self.GROUP_PREFIX, group_name)
                    print("---> Analyzing job group {}".format(job_id))
                    deps = job.controller.get_dependency_set(
                        job, self._pull_solution
                    )
                    print("the deps of the group: {}".format(deps))
                    # We are ordering a group
            else:
                # If we are in a group, we only care about the dependencies
                # inside the group
                if job_id not in self._groups[self._current_group]:
                    continue

            try:
                # We look up the job only in the map of pulled jobs
                print("**> next job will be {}".format(job_id))
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
                self._visit(next_job, trail, pull=False)
                trail.pop()

        # We've visited (recursively) all dependencies of this node, so we
        # can change the state to finished and append it to the solution
        # print(("Appending %r to order solution"), job)
        self._job_state_map[job.id] = State.FINISHED
        self._order_solution.append(job)

    def group_of(self, job_id: str):
        """Return the group that contains *job_id* (or None if not found)."""
        for g, jobs in self._groups.items():
            if job_id in jobs:
                return g
        return None

    def create_groups(self):
        """
        Create groups based on the jobs in the pulled solution.

        This method will create groups based on the jobs in the pulled
        solution and replace the jobs in the order solution with the group
        jobs.
        """
        # Create a map of groups
        self._groups = {}
        self._jobs_in_groups = {}
        self._external_deps = {}

        for job in self._pull_solution:
            if hasattr(job, "group") and job.group is not None:
                # Check if the group is already in the map
                if job.group not in self._groups:
                    self._groups[job.group] = []
                self._groups[job.group].append(job.id)
                self._jobs_in_groups[job.id] = job.group

        for group in self._groups:
            self._external_deps[group] = self.get_external_dependencies(group)

    def get_external_dependencies(self, group):
        """
        Get the external dependencies for the groups as an after string.
        """

        external_deps = set()
        for job_id in self._groups[group]:
            # Get the dependencies for the job
            job = self._pulled_map[job_id]
            deps = job.controller.get_dependency_set(job, self._pulled_map)
            # Filter out the dependencies that are not external
            for dep_type, job_id in deps:
                if self._jobs_in_groups.get(job_id) != group:
                    external_deps.add(job_id)
        return external_deps

    def replace_jobs_by_groups(self, solution):
        """
        Replace the jobs in the pulled map with the group jobs.

        This method will replace the jobs in the pulled map with the group
        jobs. It will also update the order solution to reflect the changes.
        """
        replaced_solution = []
        added_groups = []

        for job in solution:
            if job.id in self._jobs_in_groups:
                group_name = self._jobs_in_groups[job.id]
                if group_name not in added_groups:
                    # Create a new job with the group name
                    group_job_id = "{}{}".format(self.GROUP_PREFIX, group_name)
                    deps = self._external_deps[group_name]
                    group_job = JobDefinition(
                        {"id": group_job_id, "after": " ".join(deps)}
                    )
                    self._pulled_map[group_job_id] = group_job
                    self._job_state_map[group_job_id] = State.NOT_VISITED
                    print(
                        "*-*adding the job to the state map: {}".format(
                            group_job_id
                        )
                    )
                    print(self._job_state_map[group_job_id])
                    replaced_solution.append(group_job)
                    added_groups.append(group_name)
                    print("the deps of the group: {}".format(deps))
            else:
                # If the job is not in a group, just add it to the solution
                replaced_solution.append(job)

        return replaced_solution

    def replace_groups_by_jobs(self, solution):
        """
        Replace the group jobs with the original jobs inside the group.
        """

        replaced_solution = []
        for job in solution:
            if job.id.startswith(self.GROUP_PREFIX):
                group_name = job.id.split(self.GROUP_PREFIX)[1]
                # Replace the group job with the jobs inside the group in the
                # same position
                replaced_solution.extend(self._group_solutions[group_name])
                print(
                    "---->>> REPLACING group job {} with jobs: {}".format(
                        job.id, self._group_solutions[group_name]
                    )
                )
            else:
                # If the job is not a group job, just add it to the solution
                replaced_solution.append(job)

        print("---->>>Replaced solution: {}".format(replaced_solution))

        return replaced_solution

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
