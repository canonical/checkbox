# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.session.state` -- session state handling
============================================================
"""
import json
import logging
import os
import shutil
import tempfile

from plainbox.abc import IJobResult
from plainbox.impl.depmgr import DependencyError, DependencyDuplicateError
from plainbox.impl.depmgr import DependencySolver
from plainbox.impl.job import JobDefinition
from plainbox.impl.resource import ExpressionCannotEvaluateError
from plainbox.impl.resource import ExpressionFailedError
from plainbox.impl.resource import Resource
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.rfc822 import RFC822SyntaxError
from plainbox.impl.rfc822 import gen_rfc822_records
from plainbox.impl.session.jobs import (
    JobState, JobReadinessInhibitor, UndesiredJobReadinessInhibitor)

logger = logging.getLogger("plainbox.session.state")


class SessionMetadata:
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

    def __init__(self):
        self._title = None
        self._flags = set()
        self._running_job_name = None

    def as_json(self):
        """
        JSON serializable version of the meta-data
        """
        return {
            "title": self._title,
            "flags": list(sorted(self._flags)),
            "running_job_name": self._running_job_name
        }

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
        name of the running job

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


class _LegacySessionState:
    """
    Legacy features of SessionState that are being deprecated and replaced
    """

    session_data_filename = 'session.json'

    def __init__(self):
        # Temporary directory used as 'scratch space' for running jobs. Removed
        # entirely when session is terminated. Internally this is exposed as
        # $CHECKBOX_DATA to script environment.
        self._session_dir = None

        # Directory used to store jobs IO logs.
        self._jobs_io_log_dir = None

    @property
    def session_dir(self):
        """
        pathname of a temporary directory for this session

        This is not None only between calls to open() / close().
        """
        return self._session_dir

    @property
    def jobs_io_log_dir(self):
        """
        pathname of the jobs IO logs directory

        This is not None only between calls to open() / close().
        """
        return self._jobs_io_log_dir

    def open(self):
        """
        Open session state for running jobs.

        This function creates the cache directory where jobs can store their
        data. See:
        http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
        """
        if self._session_dir is None:
            xdg_cache_home = os.environ.get('XDG_CACHE_HOME') or \
                os.path.join(os.path.expanduser('~'), '.cache')
            self._session_dir = os.path.join(
                xdg_cache_home, 'plainbox', 'last-session')
            if not os.path.isdir(self._session_dir):
                os.makedirs(self._session_dir)
        if self._jobs_io_log_dir is None:
            self._jobs_io_log_dir = os.path.join(self._session_dir, 'io-logs')
            if not os.path.isdir(self._jobs_io_log_dir):
                os.makedirs(self._jobs_io_log_dir)
        return self

    def clean(self):
        """
        Clean the session directory.
        """
        if self._session_dir is not None:
            shutil.rmtree(self._session_dir)
            self._session_dir = None
            self._jobs_io_log_dir = None
            self.open()

    def close(self):
        """
        Close the session.

        It is automatically called by __exit__, the context manager exit
        function.
        """
        self._session_dir = None
        self._jobs_io_log_dir = None

    def previous_session_file(self):
        """
        Check the filesystem for previous session data
        Returns the full pathname to the session file if it exists
        """
        session_filename = os.path.join(self._session_dir,
                                        self.session_data_filename)
        if os.path.exists(session_filename):
            return session_filename
        else:
            return None

    def persistent_save(self):
        """
        Save to disk the minimum needed to resume plainbox where it stopped
        """
        # Ensure an atomic update of the session file:
        #   - create a new temp file (on the same file system!)
        #   - write data to the temp file
        #   - fsync() the temp file
        #   - rename the temp file to the appropriate name
        #   - fsync() the containing directory
        # Calling fsync() does not necessarily ensure that the entry in the
        # directory containing the file has also reached disk.
        # For that an explicit fsync() on a file descriptor for the directory
        # is also needed.
        filename = os.path.join(self._session_dir,
                                self.session_data_filename)

        with tempfile.NamedTemporaryFile(mode='wt',
                                         encoding='UTF-8',
                                         suffix='.tmp',
                                         prefix='session',
                                         dir=self._session_dir,
                                         delete=False) as tmpstream:
            # Save the session state to disk
            json.dump(self, tmpstream, cls=SessionStateEncoder,
                      ensure_ascii=False, indent=None, separators=(',', ':'))

            tmpstream.flush()
            os.fsync(tmpstream.fileno())

        session_dir_fd = os.open(self._session_dir, os.O_DIRECTORY)
        os.rename(tmpstream.name, filename)
        os.fsync(session_dir_fd)
        os.close(session_dir_fd)

    def resume(self):
        """
        Erase the job_state_map and desired_job_list with the saved ones
        """
        with open(self.previous_session_file(), 'rt', encoding='UTF-8') as f:
            previous_session = json.load(
                f, object_hook=SessionStateEncoder().dict_to_object)
        self._job_state_map = previous_session._job_state_map
        desired_job_list = []
        for job in previous_session._desired_job_list:
            if job in self._job_list:
                desired_job_list.extend(
                    [j for j in self._job_list if j == job])
            elif (previous_session._job_state_map[job.name].result.outcome !=
                    IJobResult.OUTCOME_NONE):
                # Keep jobs results from the previous session without a
                # definition in the current job_list only if they have
                # a valid result
                desired_job_list.append(job)
        self.update_desired_job_list(desired_job_list)
        # FIXME: Restore io_logs from files

    def _get_persistance_subset(self):
        state = {}
        state['_job_state_map'] = self._job_state_map
        state['_desired_job_list'] = self._desired_job_list
        return state

    @classmethod
    def from_json_record(cls, record):
        """
        Create a SessionState instance from JSON record
        """
        obj = cls([])
        obj._job_state_map = record['_job_state_map']
        obj._desired_job_list = record['_desired_job_list']
        return obj

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SessionState(_LegacySessionState):
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

        Mapping from job name to :class:`JobState`. This basically has the test
        result and the inhibitor of each job. It also serves as a
        :attr:`plainbox.impl.job.JobDefinition.name`-> job lookup helper.

        Directly exposed with the intent to fuel part of the UI. This is a way
        to get at the readiness state, result and readiness inhibitors, if any.

        XXX: this can loose data job_list has jobs with the same name. It would
        be better to use job id as the keys here. A separate map could be used
        for the name->job lookup. This will be fixed when session controller
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

        A mapping from resource name to a list of
        :class:`plainbox.impl.resource.Resource` objects. This encapsulates all
        "knowledge" about the system plainbox is running on.

        It is needed to compute job readiness (as it stores resource data
        needed by resource programs). It is also available to exporters.

        This is computed internally from the output of checkbox resource jobs,
        it can only be changed by calling :meth:`update_job_result()`

    :ivar dict metadata: instance of :class:`SessionMetadata`
    """

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
        self._job_state_map = {job.name: JobState(job)
                               for job in self._job_list}
        self._desired_job_list = []
        self._run_list = []
        self._resource_map = {}
        self._metadata = SessionMetadata()
        super(SessionState, self).__init__()

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

        Returns a tuple of which the first element is the estimated duration
        for automated jobs only and the second element is the estimated
        duration for manual jobs only - these can be easily combined.
        """
        estimate_automated = 0.0
        estimate_manual = 0.0
        for job in self._run_list:
            command_duration = job.estimated_duration if \
                               job.estimated_duration else 0.0
            # We add 30 seconds to the run time for manual jobs to
            # account for extra time taken in reading the description
            # and performing any necessary steps
            if job.automated:
                estimate_manual += command_duration
            else:
                estimate_automated += manual_overhead + command_duration

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
        with the same name.
        """
        assert job in self._job_list
        # Store the result in job_state_map
        self._job_state_map[job.name].result = result
        # Treat some jobs specially and interpret their output
        if job.plugin == "resource":
            self._process_resource_result(job, result)
        elif job.plugin == "local":
            self._process_local_result(job, result)
        # Update all job readiness state
        self._recompute_job_readiness()

    def add_job(self, new_job):
        """
        Add a new job to the session

        :param new_job: the job being added

        :raises DependencyDuplicateError:
            if a duplicate, clashing job definition is detected

        The new_job gets added to all the state tracking objects of the
        session.  The job is initially not selected to run (it is not in the
        desired_job_list and has the undesired inhibitor).

        The new_job may clash with an existing job with the same name. Unless
        both jobs are identical this will cause DependencyDuplicateError to be
        raised. Identical jobs are silently discarded.

        .. note::

            This method recomputes job readiness for all jobs
        """
        # See if we have a job with the same name already
        try:
            existing_job = self._job_state_map[new_job.name].job
        except KeyError:
            logger.info("Storing new job %r", new_job)
            # Register the new job in our state
            self._job_state_map[new_job.name] = JobState(new_job)
            self._job_list.append(new_job)
        else:
            # If there is a clash report DependencyDuplicateError only when the
            # hashes are different. This prevents a common "problem" where
            # "__foo__" local jobs just load all jobs from the "foo" category.
            if new_job != existing_job:
                raise DependencyDuplicateError(existing_job, new_job)
        # Update all job readiness state
        self._recompute_job_readiness()

    def set_resource_list(self, resource_name, resource_list):
        """
        Add or change a resource with the given name.

        Resources silently overwrite any old resources with the same name.
        """
        self._resource_map[resource_name] = resource_list

    def _process_resource_result(self, job, result):
        new_resource_list = []
        for record in self._gen_rfc822_records_from_io_log(job, result):
            # XXX: Consider forwarding the origin object here.  I guess we
            # should have from_frc822_record as with JobDefinition
            resource = Resource(record.data)
            logger.info("Storing resource record %r: %s", job.name, resource)
            new_resource_list.append(resource)
        # Replace any old resources with the new resource list
        self._resource_map[job.name] = new_resource_list

    def _process_local_result(self, job, result):
        # First parse all records and create a list of new jobs (confusing
        # name, not a new list of jobs)
        new_job_list = []
        for record in self._gen_rfc822_records_from_io_log(job, result):
            new_job = job.create_child_job_from_record(record)
            new_job_list.append(new_job)
        # Then for each new job, add it to the job_list, unless it collides
        # with another job with the same name.
        for new_job in new_job_list:
            try:
                existing_job = self._job_state_map[new_job.name].job
            except KeyError:
                logger.info("Storing new job %r", new_job)
                self._job_state_map[new_job.name] = JobState(new_job)
                self._job_list.append(new_job)
            else:
                # XXX: there should be a channel where such errors could be
                # reported back to the UI layer. Perhaps update_job_result()
                # could simply return a list of problems in a similar manner
                # how update_desired_job_list() does.
                if new_job != existing_job:
                    logging.warning(
                        ("Local job %s produced job %r that collides with"
                         " an existing job %r, the new job was discarded"),
                        job, new_job, existing_job)
                else:
                    if not existing_job.via:
                        existing_job._via = new_job.via

    def _gen_rfc822_records_from_io_log(self, job, result):
        logger.debug("processing output from a job: %r", job)
        # Select all stdout lines from the io log
        line_gen = (record[2].decode('UTF-8', errors='replace')
                    for record in result.io_log
                    if record[1] == 'stdout')
        try:
            # Parse rfc822 records from the subsequent lines
            for record in gen_rfc822_records(line_gen):
                yield record
        except RFC822SyntaxError as exc:
            # When this exception happens we will _still_ store all the
            # preceding records. This is worth testing
            logger.warning(
                "local script %s returned invalid RFC822 data: %s",
                job, exc)

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
        Map from job name to JobState that encodes the state of each job.
        """
        return self._job_state_map

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
            job_state = self._job_state_map[job.name]
            # Remove the undesired inhibitor as we want to run this job
            job_state.readiness_inhibitor_list.remove(
                UndesiredJobReadinessInhibitor)
            # Check if all job resource requirements are met
            prog = job.get_resource_program()
            if prog is not None:
                try:
                    prog.evaluate_or_raise(self._resource_map)
                except ExpressionCannotEvaluateError as exc:
                    # Lookup the related job (the job that provides the
                    # resources needed by the expression that cannot be
                    # evaluated)
                    related_job = self._job_state_map[
                        exc.expression.resource_name].job
                    # Add A PENDING_RESOURCE inhibitor as we are unable to
                    # determine if the resource requirement is met or not. This
                    # can happen if the resource job did not ran for any reason
                    # (it can either be prevented from running by normal means
                    # or simply be on the run_list but just was not executed
                    # yet).
                    inhibitor = JobReadinessInhibitor(
                        cause=JobReadinessInhibitor.PENDING_RESOURCE,
                        related_job=related_job,
                        related_expression=exc.expression)
                    job_state.readiness_inhibitor_list.append(inhibitor)
                except ExpressionFailedError as exc:
                    # Lookup the related job (the job that provides the
                    # resources needed by the expression that failed)
                    related_job = self._job_state_map[
                        exc.expression.resource_name].job
                    # Add a FAILED_RESOURCE inhibitor as we have all the data
                    # to run the requirement program but it simply returns a
                    # non-True value. This typically indicates a missing
                    # software package or necessary hardware.
                    inhibitor = JobReadinessInhibitor(
                        cause=JobReadinessInhibitor.FAILED_RESOURCE,
                        related_job=related_job,
                        related_expression=exc.expression)
                    job_state.readiness_inhibitor_list.append(inhibitor)
            # Check if all job dependencies ran successfully
            for dep_name in sorted(job.get_direct_dependencies()):
                dep_job_state = self._job_state_map[dep_name]
                # If the dependency did not have a chance to run yet add the
                # PENDING_DEP inhibitor.
                if dep_job_state.result.outcome == IJobResult.OUTCOME_NONE:
                    inhibitor = JobReadinessInhibitor(
                        cause=JobReadinessInhibitor.PENDING_DEP,
                        related_job=dep_job_state.job)
                    job_state.readiness_inhibitor_list.append(inhibitor)
                # If the dependency is anything but successful add the
                # FAILED_DEP inhibitor. In theory the PENDING_DEP code above
                # could be discarded but this would loose context and would
                # prevent the operator from actually understanding why a job
                # cannot run.
                elif dep_job_state.result.outcome != IJobResult.OUTCOME_PASS:
                    inhibitor = JobReadinessInhibitor(
                        cause=JobReadinessInhibitor.FAILED_DEP,
                        related_job=dep_job_state.job)
                    job_state.readiness_inhibitor_list.append(inhibitor)


class SessionStateEncoder(json.JSONEncoder):

    _CLS_MAP = {
        DiskJobResult: 'JOB_RESULT(d)',
        JobDefinition: 'JOB_DEFINITION',
        JobState: 'JOB_STATE',
        MemoryJobResult: 'JOB_RESULT(m)',
        SessionState: 'SESSION_STATE',
    }

    _CLS_RMAP = {value: key for key, value in _CLS_MAP.items()}

    def default(self, obj):
        """
        JSON Serialize helper to encode SessionState attributes
        Convert objects to a dictionary of their representation
        """
        if isinstance(obj, tuple(self._CLS_MAP.keys())):
            d = {'_class_id': self._CLS_MAP[obj.__class__]}
            d.update(obj._get_persistance_subset())
            return d
        else:
            return json.JSONEncoder.default(self, obj)

    def dict_to_object(self, data):
        """
        JSON Decoder helper
        Convert dictionary to python objects
        """
        if '_class_id' in data:
            cls = self._CLS_RMAP[data['_class_id']]
            return cls.from_json_record(data)
        else:
            return data
