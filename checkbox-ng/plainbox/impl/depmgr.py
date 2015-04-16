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

from plainbox.i18n import gettext as _
from plainbox.vendor import enum


logger = getLogger("plainbox.depmgr")


class DependencyError(Exception, metaclass=ABCMeta):

    """ Exception raised when a dependency error is detected. """

    @abstractproperty
    def affected_job(self):
        """ job that is affected by the dependency error. """

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
        """ Initialize a new DependencyUnknownError with a given job. """
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
        """ Get a printable description of an error. """
        return _("unknown job referenced: {!a}").format(self.job.id)

    def __repr__(self):
        """ Get a debugging representation of an error. """
        return "<{} job:{!r}>".format(self.__class__.__name__, self.job)

    def __eq__(self, other):
        """ Check if one error is equal to another. """
        if not isinstance(other, DependencyUnknownError):
            return NotImplemented
        return self.job == other.job

    def __hash__(self):
        """ Calculate the hash of an error. """
        return hash((self.job,))


class DependencyCycleError(DependencyError):

    """ Exception raised when a cyclic dependency is detected. """

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
        """ Get a printable description of an error. """
        return _("dependency cycle detected: {}").format(
            " -> ".join([job.id for job in self.job_list]))

    def __repr__(self):
        """ Get a debugging representation of an error. """
        return "<{} job_list:{!r}>".format(
            self.__class__.__name__, self.job_list)


class DependencyMissingError(DependencyError):

    """ Exception raised when a job has an unsatisfied dependency.  """

    DEP_TYPE_RESOURCE = "resource"
    DEP_TYPE_DIRECT = "direct"

    def __init__(self, job, missing_job_id, dep_type):
        """ Initialize a new error with given data. """
        self.job = job
        self.missing_job_id = missing_job_id
        self.dep_type = dep_type

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
        """ Get a printable description of an error. """
        return _("missing dependency: {!r} ({})").format(
            self.missing_job_id, self.dep_type)

    def __repr__(self):
        """ Get a debugging representation of an error. """
        return "<{} job:{!r} missing_job_id:{!r} dep_type:{!r}>".format(
            self.__class__.__name__,
            self.job, self.missing_job_id, self.dep_type)

    def __eq__(self, other):
        """ Check if one error is equal to another. """
        if not isinstance(other, DependencyMissingError):
            return NotImplemented
        return (self.job == other.job
                and self.missing_job_id == other.missing_job_id
                and self.dep_type == other.dep_type)

    def __hash__(self):
        """ Calculate the hash of an error. """
        return hash((self.job, self.missing_job_id, self.dep_type))


class DependencyDuplicateError(DependencyError):

    """ Exception raised when two jobs have the same id.  """

    def __init__(self, job, duplicate_job):
        """ Initialize a new error with given data. """
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
        """ Get a printable description of an error. """
        return _("duplicate job id: {!r}").format(self.affected_job.id)

    def __repr__(self):
        """ Get a debugging representation of an error. """
        return "<{} job:{!r} duplicate_job:{!r}>".format(
            self.__class__.__name__, self.job, self.duplicate_job)


class Color(enum.Enum):

    """
    Three classic colors for recursive graph visitor.

    WHITE:
        For nodes have not been visited yet.
    GRAY:
        For nodes that are currently being visited but the visit is not
        complete.
    BLACK:
        For nodes that have been visited and are complete.
    """

    WHITE = 'white'
    GRAY = 'gray'
    BLACK = 'black'


class DependencySolver:

    """
    Dependency solver for Jobs.

    Uses a simple depth-first search to discover the sequence of jobs that can
    run. Use the resolve_dependencies() class method to get the solution.
    """

    COLOR_WHITE = Color.WHITE
    COLOR_GRAY = Color.GRAY
    COLOR_BLACK = Color.BLACK

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
        # Job colors, maps from job.id to COLOR_xxx
        self._job_color_map = {job.id: self.COLOR_WHITE for job in job_list}
        # The computed solution, made out of job instances. This is not
        # necessarily the only solution but the algorithm computes the same
        # value each time, given the same input.
        self._solution = []

    def _solve(self, visit_list=None):
        """
        Internal method of DependencySolver.

        Solves the dependency graph and returns the solution.

        Calls _visit() on each of the initial nodes/jobs
        """
        # Visit the visit list
        logger.debug(_("Starting solve"))
        logger.debug(_("Solver job list: %r"), self._job_list)
        logger.debug(_("Solver visit list: %r"), visit_list)
        if visit_list is None:
            visit_list = self._job_list
        for job in visit_list:
            self._visit(job)
        logger.debug(_("Done solving"))
        # Return the solution
        return self._solution

    def _visit(self, job, trail=None):
        """
        Internal method of DependencySolver.

        Called each time a node is visited. Nodes already seen in _visited are
        skipped. Attempts to enumerate all dependencies (both direct and
        resource) and resolve them. Missing jobs cause DependencyMissingError
        to be raised. Calls _visit recursively on all dependencies.
        """
        try:
            color = self._job_color_map[job.id]
        except KeyError:
            logger.debug(_("Visiting job that's not on the job_list: %r"), job)
            raise DependencyUnknownError(job)
        logger.debug(_("Visiting job %s (color %s)"), job.id, color)
        if color == self.COLOR_WHITE:
            # This node has not been visited yet. Let's mark it as GRAY (being
            # visited) and iterate through the list of dependencies
            self._job_color_map[job.id] = self.COLOR_GRAY
            # If the trail was not specified start a trail for this node
            if trail is None:
                trail = [job]
            for dep_type, job_id in job.controller.get_dependency_set(job):
                # Dependency is just an id, we need to resolve it
                # to a job instance. This can fail (missing dependencies)
                # so let's guard against that.
                try:
                    next_job = self._job_map[job_id]
                except KeyError:
                    logger.debug(_("Found missing dependency: %r from %r"),
                                 job_id, job)
                    raise DependencyMissingError(job, job_id, dep_type)
                else:
                    # For each dependency that we visit let's reuse the trail
                    # to give proper error messages if a dependency loop exists
                    logger.debug(_("Visiting dependency: %r"), next_job)
                    # Update the trail as we visit that node
                    trail.append(next_job)
                    self._visit(next_job, trail)
                    trail.pop()
            # We've visited (recursively) all dependencies of this node,
            # let's color it black and append it to the solution list.
            logger.debug(_("Appending %r to solution"), job)
            self._job_color_map[job.id] = self.COLOR_BLACK
            self._solution.append(job)
        elif color == self.COLOR_GRAY:
            # This node is not fully traced yet but has been visited already
            # so we've found a dependency loop. We need to cut the initial
            # part of the trail so that we only report the part that actually
            # forms a loop
            trail = trail[trail.index(job):]
            logger.debug(_("Found dependency cycle: %r"), trail)
            raise DependencyCycleError(trail)
        else:
            assert color == self.COLOR_BLACK
            # This node has been visited and is fully traced.
            # We can just skip it and go back

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
