# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.session.state` -- session state handling
============================================================
"""
import logging

from plainbox.i18n import gettext as _
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.depmgr import DependencyError
from plainbox.impl.depmgr import DependencySolver
from plainbox.impl.session.jobs import JobState
from plainbox.impl.session.jobs import UndesiredJobReadinessInhibitor
from plainbox.impl.signal import Signal


logger = logging.getLogger("plainbox.session.state")


class SessionMetaData:
    """
    Class representing non-critical state of the session.

    The data held here allows applications to reason about sessions in general
    but is not relevant to the runner or the core in general
    """

    # Flag indicating that the testing session is not complete and additional
    # testing is expected. Applications are encouraged to add this flag
    # immediately after creating a new session. Applications are also
    # encouraged to remove this flag after the expected test plan is complete
    FLAG_INCOMPLETE = "incomplete"

    # Flag indicating that results of this testing session have been submitted
    # to some central results repository. Applications are encouraged to
    # set this flag after successfully sending the result somewhere.
    FLAG_SUBMITTED = "submitted"

    def __init__(self, title=None, flags=None, running_job_name=None,
                 app_blob=None, app_id=None):
        if flags is None:
            flags = []
        self._title = title
        self._flags = set(flags)
        self._running_job_name = running_job_name
        self._app_blob = app_blob
        self._app_id = app_id

    def __repr__(self):
        return "<{} title:{!r} flags:{!r} running_job_name:{!r}>".format(
            self.__class__.__name__, self.title, self.flags,
            self.running_job_name)

    @property
    def title(self):
        """
        the session title.

        Title is just an arbitrary string that can be used to distinguish
        between multiple sessions.

        The value can be changed at any time.
        """
        return self._title

    @title.setter
    def title(self, title):
        self._title = title

    @property
    def flags(self):
        """
        a set of flags that are associated with this session.

        This set is persisted by persistent_save() and can be used to keep
        track of how the application wants to interpret this session state.

        Intended usage is to keep track of "testing finished" and
        "results submitted" flags. Some flags are added as constants to this
        class.
        """
        return self._flags

    @flags.setter
    def flags(self, flags):
        self._flags = flags

    @property
    def running_job_name(self):
        """
        id of the running job

        .. note::
            This property has a confusing name. It actually refers to job ID,
            not name.

        This property should be updated to keep track of the name of the
        job that is being executed. When either plainbox or the machine it
        was running on crashes during the execution of a job this value
        should be preserved and can help the GUI to resume and provide an
        error message.

        The property MUST be set before starting the job itself.
        """
        return self._running_job_name

    @running_job_name.setter
    def running_job_name(self, running_job_name):
        self._running_job_name = running_job_name

    @property
    def app_blob(self):
        """
        Custom, application specific binary blob.

        The type and value of this property is irrelevant as it is not
        inspected by plainbox at all. Reasonable applications will not make use
        of this property for storing large amounts of data. If you are tempted
        to do that, please redesign your application or propose changes to
        plainbox.
        """
        return self._app_blob

    @app_blob.setter
    def app_blob(self, value):
        if value is not None and not isinstance(value, bytes):
            # TRANSLATORS: please don't translate app_blob, None and bytes
            raise TypeError(_("app_blob must be either None or bytes"))
        self._app_blob = value

    @property
    def app_id(self):
        """
        Application identifier

        A string identifying the application that stored app_blob. It is
        recommended to use reverse domain names or UUIDs.
        """
        return self._app_id

    @app_id.setter
    def app_id(self, value):
        if value is not None and not isinstance(value, str):
            # TRANSLATORS: please don't translate app_blob, None and bytes
            raise TypeError(_("app_id must be either None or str"))
        self._app_id = value


class SessionState:
    """
    Class representing all state needed during a single program session.

    This is the central glue/entry-point for applications. It connects user
    intents to the rest of the system / plumbing and keeps all of the state in
    one place.

    The set of utility methods and properties allow applications to easily
    handle the lower levels of dependencies, resources and ready states.

    :class:`SessionState` has the following instance variables, all of which
    are currently exposed as properties.

    :ivar list job_list: A list of all known jobs

        Not all the jobs from this list are going to be executed (or selected
        for execution) by the user.

        It may change at runtime because of local jobs. Note that in upcoming
        changes this will start out empty and will be changeable dynamically.
        It can still change due to local jobs but there is no API yes.

        This list cannot have any duplicates, if that is the case a
        :class:`DependencyDuplicateError` is raised. This has to be handled
        externally and is a sign that the job database is corrupted or has
        wrong data. As an exception if duplicates are perfectly identical this
        error is silently corrected.

    :ivar dict job_state_map: mapping that tracks the state of each job

        Mapping from job id to :class:`JobState`. This basically has the test
        result and the inhibitor of each job. It also serves as a
        :attr:`plainbox.impl.job.JobDefinition.id`-> job lookup helper.

        Directly exposed with the intent to fuel part of the UI. This is a way
        to get at the readiness state, result and readiness inhibitors, if any.

        XXX: this can loose data job_list has jobs with the same id. It would
        be better to use job id as the keys here. A separate map could be used
        for the id->job lookup. This will be fixed when session controller
        branch lands in trunk as then jobs are dynamically added to the system
        one at a time and proper error conditions can be detected and reported.

    :ivar list desired_job_list: subset of jobs selected for execution

        This is used to compute :attr:`run_list`. It can only be changed by
        calling :meth:`update_desired_job_list()` which returns meaningful
        values so this is not a settable property.

    :ivar list run_list: sorted list of jobs to execute

        This is basically a superset of desired_job_list and a subset of
        job_list that is topologically sorted to allowing all desired jobs to
        run. This property is updated whenever desired_job_list is changed.

    :ivar dict resource_map: all known resources

        A mapping from resource id to a list of
        :class:`plainbox.impl.resource.Resource` objects. This encapsulates all
        "knowledge" about the system plainbox is running on.


        It is needed to compute job readiness (as it stores resource data
        needed by resource programs). It is also available to exporters.

        This is computed internally from the output of checkbox resource jobs,
        it can only be changed by calling :meth:`update_job_result()`

    :ivar dict metadata: instance of :class:`SessionMetaData`
    """

    @Signal.define
    def on_job_state_map_changed(self):
        """
        Signal fired after job_state_map is changed in any way.

        This signal is always fired before any more specialized signals
        such as :meth:`on_job_result_changed()` and :meth:`on_job_added()`.

        This signal is fired pretty often, each time a job result is
        presented to the session and each time a job is added. When
        both of those events happen at the same time only one notification
        is sent. The actual state is not sent as it is quite extensive
        and can be easily looked at by the application.
        """

    @Signal.define
    def on_job_result_changed(self, job, result):
        """
        Signal fired after a job get changed (set)

        This signal is fired each time a result is presented to the session.

        This signal is fired **after** :meth:`on_job_state_map_changed()`
        """
        logger.info(_("Job %s result changed to %r"), job, result)

    @Signal.define
    def on_job_added(self, job):
        """
        Signal sent whenever a job is added to the session.

        This signal is fired **after** :meth:`on_job_state_map_changed()`
        """
        logger.info(_("New job defined: %r"), job)

    @Signal.define
    def on_job_removed(self, job):
        """
        Signal sent whenever a job is removed from the session.

        This signal is fired **after** :meth:`on_job_state_map_changed()`
        """
        logger.info(_("Job removed: %r"), job)

    def __init__(self, job_list):
        """
        Initialize a new SessionState with a given list of jobs.

        The jobs are all of the jobs that the session knows about.
        """
        # Start by making a copy of job_list as we may modify it below
        job_list = job_list[:]
        while True:
            try:
                # Construct a solver with the job list as passed by the caller.
                # This will do a little bit of validation and might raise
                # DepdendencyDuplicateError if there are any duplicates at this
                # stage.
                #
                # There's a single case that is handled here though, if both
                # jobs are identical this problem is silently fixed. This
                # should not happen in normal circumstances but is non the less
                # harmless (as long as both jobs are perfectly identical)
                #
                # Since this problem can happen any number of times (many
                # duplicates) this is performed in a loop. The loop breaks when
                # we cannot solve the problem _OR_ when no error occurs.
                DependencySolver(job_list)
            except DependencyDuplicateError as exc:
                # If both jobs are identical then silently fix the problem by
                # removing one of the jobs (here the second one we've seen but
                # it's not relevant as they are possibly identical) and try
                # again
                if exc.job == exc.duplicate_job:
                    job_list.remove(exc.duplicate_job)
                    continue
                else:
                    # If the jobs differ report this back to the caller
                    raise
            else:
                # If there are no problems then break the loop
                break
        self._job_list = job_list
        self._job_state_map = {job.id: JobState(job)
                               for job in self._job_list}
        self._desired_job_list = []
        self._run_list = []
        self._resource_map = {}
        self._metadata = SessionMetaData()
        super(SessionState, self).__init__()

    def trim_job_list(self, qualifier):
        """
        Discard jobs that are selected by the given qualifier.

        :param qualifier:
            A qualifier that selects jobs to be removed
        :ptype qualifier:
            IJobQualifier

        :raises ValueError:
            If any of the jobs selected by the qualifier is on the desired job
            list (or the run list)

        This function correctly and safely discards certain jobs from the job
        list. It also removes the associated job state (and referenced job
        result) and results (for jobs that were resource jobs)
        """
        # Build a list for each of the jobs in job_list, that tells us if we
        # should remove that job. This way we only call the qualifier once per
        # job and can do efficient operations later.
        #
        # The whole function should be O(N), where N is len(job_list)
        remove_flags = [
            qualifier.designates(job) for job in self._job_list]
        # Build a list of (job, should_remove) flags, we'll be using this list
        # a few times below.
        job_and_flag_list = list(zip(self._job_list, remove_flags))
        # Build a set of ids of jobs that we'll be removing
        remove_job_id_set = frozenset([
            job.id for job, should_remove in job_and_flag_list
            if should_remove is True])
        # Build a set of ids of jobs that are on the run list
        run_list_id_set = frozenset([job.id for job in self.run_list])
        # Check if this is safe to do. None of the jobs may be in the run list
        # (or the desired job list which is always a subset of run list)
        unremovable_job_id_set = remove_job_id_set.intersection(
            run_list_id_set)
        if unremovable_job_id_set:
            raise ValueError(
                _("cannot remove jobs that are on the run list: {}").format(
                    ', '.join(sorted(unremovable_job_id_set))))
        # Remove job state and resources (if present) for all the jobs we're
        # about to remove. Note that while each job has a state object not all
        # jobs generated resources so that removal is conditional.
        for job, should_remove in job_and_flag_list:
            if should_remove:
                del self._job_state_map[job.id]
                if job.id in self._resource_map:
                    del self._resource_map[job.id]
        # Compute a list of jobs to retain
        retain_list = [
            job for job, should_remove in job_and_flag_list
            if should_remove is False]
        # And a list of jobs to remove
        remove_list = [
            job for job, should_remove in job_and_flag_list
            if should_remove is True]
        # Replace job list with the filtered list
        self._job_list = retain_list
        if remove_list:
            # Notify that the job state map has changed
            self.on_job_state_map_changed()
            # And that each removed job was actually removed
            for job in remove_list:
                self.on_job_removed(job)

    def update_desired_job_list(self, desired_job_list):
        """
        Update the set of desired jobs (that ought to run)

        This method can be used by the UI to recompute the dependency graph.
        The argument 'desired_job_list' is a list of jobs that should run.
        Those jobs must be a sub-collection of the job_list argument that was
        passed to the constructor.

        It never fails although it may reduce the actual permitted
        desired_job_list to an empty list. It returns a list of problems (all
        instances of DependencyError class), one for each job that had to be
        removed.
        """
        # Remember a copy of original desired job list. We may modify this list
        # so let's not mess up data passed by the caller.
        self._desired_job_list = list(desired_job_list)
        # Reset run list just in case desired_job_list is empty
        self._run_list = []
        # Try to solve the dependency graph. This is done in a loop as may need
        # to remove a problematic job and re-try. The loop provides a stop
        # condition as we will eventually run out of jobs.
        problems = []
        while self._desired_job_list:
            # XXX: it might be more efficient to incorporate this 'recovery
            # mode' right into the solver, this way we'd probably save some
            # resources or runtime complexity.
            try:
                self._run_list = DependencySolver.resolve_dependencies(
                    self._job_list, self._desired_job_list)
            except DependencyError as exc:
                # When a dependency error is detected remove the affected job
                # form _desired_job_list and try again.
                self._desired_job_list.remove(exc.affected_job)
                # Remember each problem, this can be presented by the UI
                problems.append(exc)
                continue
            else:
                # Don't iterate the loop if there was no exception
                break
        # Update all job readiness state
        self._recompute_job_readiness()
        # Return all dependency problems to the caller
        return problems

    def get_estimated_duration(self, manual_overhead=30.0):
        """
        Provide the estimated duration of the jobs that have been selected
        to run in this session (maintained by calling update_desired_job_list).

        Manual jobs have an arbitrary figure added to their runtime to allow
        for execution of the test steps and verification of the result.

        :returns: (estimate_automated, estimate_manual)

        where estimate_automated is the value for automated jobs only and
        estimate_manual is the value for manual jobs only. These can be
        easily combined. Either value can be None if the  value could not be
        calculated due to any job lacking the required estimated_duration
        field.
        """
        estimate_automated = 0.0
        estimate_manual = 0.0
        for job in self._run_list:
            if job.automated and estimate_automated is not None:
                if job.estimated_duration is not None:
                    estimate_automated += job.estimated_duration
                elif job.plugin != 'local':
                    estimate_automated = None
            elif not job.automated and estimate_manual is not None:
                # We add a fixed extra amount of seconds to the run time
                # for manual jobs to account for the time taken in reading
                # the description and performing any necessary steps
                estimate_manual += manual_overhead
                if job.estimated_duration is not None:
                    estimate_manual += job.estimated_duration
                elif job.command:
                    estimate_manual = None
        return (estimate_automated, estimate_manual)

    def update_job_result(self, job, result):
        """
        Notice the specified test result and update readiness state.

        This function updates the internal result collection with the data from
        the specified test result. Results can safely override older results.
        Results also change the ready map (jobs that can run) because of
        dependency relations.

        Some results have deeper meaning, those are results for local and
        resource jobs. They are discussed in detail below:

        Resource jobs produce resource records which are used as data to run
        requirement expressions against. Each time a result for a resource job
        is presented to the session it will be parsed as a collection of RFC822
        records. A new entry is created in the resource map (entirely replacing
        any old entries), with a list of the resources that were parsed from
        the IO log.

        Local jobs produce more jobs. Like with resource jobs, their IO log is
        parsed and interpreted as additional jobs. Unlike in resource jobs
        local jobs don't replace anything. They cannot replace an existing job
        with the same id.
        """
        job.controller.observe_result(self, job, result)
        self._recompute_job_readiness()

    def add_job(self, new_job, recompute=True):
        """
        Add a new job to the session

        :param new_job:
            The job being added
        :param recompute:
            If True, recompute readiness inhibitors for all jobs.
            You should only set this to False if you're adding
            a number of jobs and will otherwise ensure that
            :meth:`_recompute_job_readiness()` gets called before
            session state users can see the state again.
        :returns:
            The job that was actually added or an existing, identical
            job if a perfect clash was silently ignored.

        :raises DependencyDuplicateError:
            if a duplicate, clashing job definition is detected

        The new_job gets added to all the state tracking objects of the
        session.  The job is initially not selected to run (it is not in the
        desired_job_list and has the undesired inhibitor).

        The new_job may clash with an existing job with the same id. Unless
        both jobs are identical this will cause DependencyDuplicateError to be
        raised. Identical jobs are silently discarded.

        .. note::

            This method recomputes job readiness for all jobs
        """
        # See if we have a job with the same id already
        try:
            existing_job = self.job_state_map[new_job.id].job
        except KeyError:
            # Register the new job in our state
            self.job_state_map[new_job.id] = JobState(new_job)
            self.job_list.append(new_job)
            self.on_job_state_map_changed()
            self.on_job_added(new_job)
            return new_job
        else:
            # If there is a clash report DependencyDuplicateError only when the
            # hashes are different. This prevents a common "problem" where
            # "__foo__" local jobs just load all jobs from the "foo" category.
            if new_job != existing_job:
                raise DependencyDuplicateError(existing_job, new_job)
            return existing_job
        finally:
            # Update all job readiness state
            if recompute:
                self._recompute_job_readiness()

    def set_resource_list(self, resource_id, resource_list):
        """
        Add or change a resource with the given id.

        Resources silently overwrite any old resources with the same id.
        """
        self._resource_map[resource_id] = resource_list

    @property
    def job_list(self):
        """
        List of all known jobs.

        Not necessarily all jobs from this list can be, or are desired to run.
        For API simplicity this variable is read-only, if you wish to alter the
        list of all jobs re-instantiate this class please.
        """
        return self._job_list

    @property
    def desired_job_list(self):
        """
        List of jobs that are on the "desired to run" list

        This is a list, not a set, because the dependency solver algorithm
        retains as much of the original ordering as possible. Having said that,
        the actual order can differ widely (for instance, be reversed)
        """
        return self._desired_job_list

    @property
    def run_list(self):
        """
        List of jobs that were intended to run, in the proper order

        The order is a result of topological sorting of the desired_job_list.
        This value is recomputed when change_desired_run_list() is called. It
        may be shorter than desired_run_list due to dependency errors.
        """
        return self._run_list

    @property
    def job_state_map(self):
        """
        Map from job id to JobState that encodes the state of each job.
        """
        return self._job_state_map

    @property
    def resource_map(self):
        """
        Map from resource id to a list of resource records
        """
        return self._resource_map

    @property
    def metadata(self):
        """
        metadata object associated with this session state.
        """
        return self._metadata

    def _recompute_job_readiness(self):
        """
        Internal method of SessionState.

        Re-computes [job_state.ready
                     for job_state in _job_state_map.values()]
        """
        # Reset the state of all jobs to have the undesired inhibitor. Since
        # we maintain a state object for _all_ jobs (including ones not in the
        # _run_list this correctly updates all values in the _job_state_map
        # (the UI can safely use the readiness state of all jobs)
        for job_state in self._job_state_map.values():
            job_state.readiness_inhibitor_list = [
                UndesiredJobReadinessInhibitor]
        # Take advantage of the fact that run_list is topologically sorted and
        # do a single O(N) pass over _run_list. All "current/update" state is
        # computed before it needs to be observed (thanks to the ordering)
        for job in self._run_list:
            job_state = self._job_state_map[job.id]
            # Remove the undesired inhibitor as we want to run this job
            job_state.readiness_inhibitor_list.remove(
                UndesiredJobReadinessInhibitor)
            # Ask the job controller about inhibitors affecting this job
            for inhibitor in job.controller.get_inhibitor_list(self, job):
                job_state.readiness_inhibitor_list.append(inhibitor)
