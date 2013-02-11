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
plainbox.impl.session
=====================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""
import json
import logging
import os
import shutil
import tempfile

from plainbox.impl.depmgr import DependencyError
from plainbox.impl.depmgr import DependencySolver
from plainbox.impl.job import JobDefinition
from plainbox.impl.resource import ExpressionCannotEvaluateError
from plainbox.impl.resource import ExpressionFailedError
from plainbox.impl.resource import Resource
from plainbox.impl.result import JobResult
from plainbox.impl.rfc822 import RFC822SyntaxError
from plainbox.impl.rfc822 import gen_rfc822_records

logger = logging.getLogger("plainbox.session")


class JobReadinessInhibitor:
    """
    Class representing the cause of a job not being ready to execute.

    It is intended to be consumed by UI layers and to provide them with enough
    information to render informative error messages or other visual feedback
    that will aid the user in understanding why a job cannot be started.

    There are four possible not ready causes:

        UNDESIRED:
            This job was not selected to run in this session

        PENDING_DEP:
           This job depends on another job which was not started yet

        FAILED_DEP:
            This job depends on another job which was started and failed

        PENDING_RESOURCE:
            This job has a resource requirement expression that uses a resource
            produced by another job which was not started yet

        FAILED_RESOURCE:
            This job has a resource requirement that evaluated to a false value

    All causes apart from UNDESIRED use the related_job property to encode a
    job that is related to the problem. The PENDING_RESOURCE and
    FAILED_RESOURCE causes also store related_expression that describes the
    relevant requirement expression.

    There are three attributes that can be accessed:

        cause:
            Encodes the reason why a job is not ready, see above.

        related_job:
            Provides additional context for the problem. This is not the job
            that is affected, rather, the job that is causing the problem.

        related_expression:
            Provides additional context for the problem caused by a failing
            resource expression.
    """
    # XXX: PENDING_RESOURCE is not strict, there are multiple states that are
    # clumped here which is something I don't like. A resource may be still
    # "pending" as in PENDING_DEP (it has not ran yet) or it could have ran but
    # failed to produce any data, it could also be prevented from running
    # because it has unmet dependencies. In essence it tells us nothing about
    # if related_job.can_start() is true or not.
    #
    # XXX: FAILED_RESOURCE is "correct" but somehow misleading, FAILED_RESOURCE
    # is used to represent a resource expression that evaluated to a non-True
    # value

    UNDESIRED, PENDING_DEP, FAILED_DEP, PENDING_RESOURCE, FAILED_RESOURCE \
        = range(5)

    _cause_display = {
        UNDESIRED: "UNDESIRED",
        PENDING_DEP: "PENDING_DEP",
        FAILED_DEP: "FAILED_DEP",
        PENDING_RESOURCE: "PENDING_RESOURCE",
        FAILED_RESOURCE: "FAILED_RESOURCE"
    }

    def __init__(self, cause, related_job=None, related_expression=None):
        """
        Initialize a new inhibitor with the specified cause.

        If cause is other than UNDESIRED a related_job is necessary. If cause
        is either PENDING_RESOURCE or FAILED_RESOURCE related_expression is
        necessary as well. A ValueError is raised when this is violated.
        """
        if cause not in self._cause_display:
            raise ValueError("unsupported value for cause")
        if cause != self.UNDESIRED and related_job is None:
            raise ValueError("related_job must not be None when cause is"
                             " {}".format(self._cause_display[cause]))
        if cause in (self.PENDING_RESOURCE, self.FAILED_RESOURCE) \
                and related_expression is None:
            raise ValueError("related_expression must not be None when cause"
                             "is {}".format(self._cause_display[cause]))
        self.cause = cause
        self.related_job = related_job
        self.related_expression = related_expression

    def __repr__(self):
        return "<{} cause:{} related_job:{!r} related_expression:{!r}>".format(
            self.__class__.__name__, self._cause_display[self.cause],
            self.related_job, self.related_expression)

    def __str__(self):
        if self.cause == self.UNDESIRED:
            return "undesired"
        elif self.cause == self.PENDING_DEP:
            return "required dependency {!r} did not run yet".format(
                self.related_job.name)
        elif self.cause == self.FAILED_DEP:
            return "required dependency {!r} has failed".format(
                self.related_job.name)
        elif self.cause == self.PENDING_RESOURCE:
            return ("resource expression {!r} could not be evaluated because"
                    " the resource it depends on did not run yet").format(
                        self.related_expression.text)
        else:
            assert self.cause == self.FAILED_RESOURCE
            return "resource expression {!r} evaluates to false".format(
                self.related_expression.text)


# A global instance of JobReadinessInhibitor with the UNDESIRED cause.
# This is used a lot and it makes no sense to instantiate all the time.
UndesiredJobReadinessInhibitor = JobReadinessInhibitor(
    JobReadinessInhibitor.UNDESIRED)


class JobState:
    """
    Class representing the state of a job in a session.

    Contains two basic properties of each job (either of which can be None):

        * the readiness_inhibitor_list that prevent the job form starting
        * the result (outcome) of the run (IJobResult)

    For convenience (to SessionState implementation) it also has a reference to
    the job itself.  This class is a pure state holder an will typically
    collaborate with the SessionState class and the UI layer.
    """

    def __init__(self, job):
        """
        Initialize a new job state object.

        The job will be inhibited by a single UNDESIRED inhibitor and will have
        a result with OUTCOME_NONE that basically says it did not run yet.
        """
        self._job = job
        self._readiness_inhibitor_list = [UndesiredJobReadinessInhibitor]
        self._result = JobResult({
            'job': job,
            'outcome': JobResult.OUTCOME_NONE
        })

    def __repr__(self):
        return ("<{} job:{!r} readiness_inhibitor_list:{!r}"
                " result:{!r}>").format(
                    self.__class__.__name__, self._job,
                    self._readiness_inhibitor_list, self._result)

    @property
    def job(self):
        """
        the job associated with this state
        """
        return self._job

    def _readiness_inhibitor_list():

        doc = "the list of readiness inhibitors of the associated job"

        def fget(self):
            return self._readiness_inhibitor_list

        def fset(self, value):
            self._readiness_inhibitor_list = value

        return (fget, fset, None, doc)

    readiness_inhibitor_list = property(*_readiness_inhibitor_list())

    def _result():
        doc = "the result of running the associated job"

        def fget(self):
            return self._result

        def fset(self, value):
            if value.job is not self.job:
                raise ValueError("result job does not match")
            self._result = value

        return (fget, fset, None, doc)

    result = property(*_result())

    def can_start(self):
        """
        Quickly check if the associated job can run right now.
        """
        return len(self._readiness_inhibitor_list) == 0

    def get_readiness_description(self):
        """
        Get a human readable description of the current readiness state
        """
        if self._readiness_inhibitor_list:
            return "job cannot be started: {}".format(
                ", ".join((str(inhibitor)
                           for inhibitor in self._readiness_inhibitor_list)))
        else:
            return "job can be started"

    def _get_persistance_subset(self):
        # Don't save resource job results, fresh data are required
        # so we can't reuse the old ones
        # The inhibitor list needs to be recomputed as well, don't save it.
        state = {}
        state['_job'] = self._job
        if self._job.plugin == 'resource':
            state['_result'] = JobResult({
                'job': self._job,
                'outcome': JobResult.OUTCOME_NONE
            })
        else:
            state['_result'] = self._result
        return state

    @classmethod
    def from_json_record(cls, record):
        """
        Create a JobState instance from JSON record
        """
        obj = cls(record['_job'])
        obj._readiness_inhibitor_list = [UndesiredJobReadinessInhibitor]
        obj._result = record['_result']
        return obj


class SessionState:
    """
    Class representing all state needed during a single program session.

    The set of utility methods and properties allow applications to easily
    handle the lower levels of dependencies, resources and ready states.

    Once instantiated with a list of known jobs it is ready to react to
    UI-driven changes. It is expected that the user will select / unselect
    and run jobs. This class can react to both actions by recomputing the
    dependency graph and updating the read states accordingly.

    Ready states (one for each job) allow the UI to take simple decisions
    (either can or cannot run)
    """

    session_data_filename = 'session.json'

    def __init__(self, job_list):
        # The original list of job that the system knows about.
        # Not all jobs from this list are going to be executed
        # (or selected for execution) by the user.
        self._job_list = job_list
        # State of each job, see JobState for details but it basically
        # has the test result and the inhibitor of each job. It also serves
        # as a job.name -> job lookup helper.
        #
        # Directly exposed with the intent to fuel part of the UI.
        #
        # XXX: this can loose data job_list has jobs with the same name. It
        # would be better to use job id as the keys here. A separate map could
        # be used for the name->job lookup.
        self._job_state_map = {job.name: JobState(job)
                               for job in self._job_list}
        # A subset of job_list that was selected by the user for execution.
        # Used to compute run_list. Can be changed at will during lifetime
        # of this object
        self._desired_job_list = []
        # Copy of desired_job_list that was topologically sorted by the
        # dependency solver. Jobs must run in this order (although not all jobs
        # may actually run or will actually be successful)
        self._run_list = []
        # A collection of known resources. Mapping resource job name to a list
        # of resource objects. Needed to compute task readiness (as it stores
        # resource data needed by resource programs). Currently not exposed
        # outside of this class.
        self._resource_map = {}
        # Temporary directory used as 'scratch space' for running jobs. Removed
        # entirely when session is terminated. Internally this is exposed as
        # $CHECKBOX_DATA to script environment.
        self._session_dir = None
        # Directory used to store jobs IO logs.
        self._jobs_io_log_dir = None

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
            temp_dir = os.path.join(xdg_cache_home, 'plainbox')
            if not os.path.isdir(temp_dir):
                os.makedirs(temp_dir)
            self._session_dir = tempfile.mkdtemp(dir=temp_dir)
        if self._jobs_io_log_dir is None:
            self._jobs_io_log_dir = os.path.join(self._session_dir, 'io-logs')
            if not os.path.isdir(self._jobs_io_log_dir):
                os.makedirs(self._jobs_io_log_dir)
        return self

    def close(self):
        """
        Close the session and remove temporary disk state.

        This function removes the directory created by .open() and all the data
        that was placed there. It is automatically called by __exit__, the
        context manager exit function. Care should be taken to ensure that all
        session data, particularly attachments, were saved before.
        """
        if self._session_dir is not None:
            shutil.rmtree(self._session_dir)
            self._session_dir = None

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
                    self._job_list, desired_job_list)
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

    def update_job_result(self, job, job_result):
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
        assert job_result.job is job
        assert job_result.job in self._job_list
        # Store the result in job_state_map
        self._job_state_map[job.name].result = job_result
        # Treat some jobs specially and interpret their output
        if job.plugin == "resource":
            self._process_resource_result(job_result)
        elif job.plugin == "local":
            self._process_local_result(job_result)
        # Update all job readiness state
        self._recompute_job_readiness()

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

    def _process_resource_result(self, result):
        new_resource_list = []
        for record in self._gen_rfc822_records_from_io_log(result):
            # XXX: Consider forwarding the origin object here.  I guess we
            # should have from_frc822_record as with JobDefinition
            resource = Resource(record.data)
            logger.info("Storing resource record %r: %s",
                        result.job.name, resource)
            new_resource_list.append(resource)
        # Replace any old resources with the new resource list
        self._resource_map[result.job.name] = new_resource_list

    def _process_local_result(self, result):
        # First parse all records and create a list of new jobs (confusing
        # name, not a new list of jobs)
        new_job_list = []
        for record in self._gen_rfc822_records_from_io_log(result):
            new_job = result.job.create_child_job_from_record(record)
            new_job_list.append(new_job)
        # Then for each new job, add it to the job_list, unless it collides
        # with another job with the same name.
        for new_job in new_job_list:
            try:
                existing_job = self._job_state_map[new_job.name]
            except KeyError:
                logger.info("Storing new job %r", new_job)
                self._job_state_map[new_job.name] = JobState(new_job)
                self._job_list.append(new_job)
            else:
                # XXX: there should be a channel where such errors could be
                # reported back to the UI layer. Perhaps update_job_result()
                # could simply return a list of problems in a similar manner
                # how update_desired_job_list() does.
                logging.warning(
                    ("Local job %s produced job %r that collides with"
                     " an existing job %r, the new job was discarded"),
                    result.job, new_job, existing_job)

    def _gen_rfc822_records_from_io_log(self, result):
        logger.debug("processing output from a job: %r", result.job)
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
                result.job, exc)

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
            for dep_name in job.get_direct_dependencies():
                dep_job_state = self._job_state_map[dep_name]
                # If the dependency did not have a chance to run yet add the
                # PENDING_DEP inhibitor.
                if dep_job_state.result.outcome == JobResult.OUTCOME_NONE:
                    inhibitor = JobReadinessInhibitor(
                        cause=JobReadinessInhibitor.PENDING_DEP,
                        related_job=dep_job_state.job)
                    job_state.readiness_inhibitor_list.append(inhibitor)
                # If the dependency is anything but successful add the
                # FAILED_DEP inhibitor. In theory the PENDING_DEP code above
                # could be discarded but this would loose context and would
                # prevent the operator from actually understanding why a job
                # cannot run.
                elif dep_job_state.result.outcome != JobResult.OUTCOME_PASS:
                    inhibitor = JobReadinessInhibitor(
                        cause=JobReadinessInhibitor.FAILED_DEP,
                        related_job=dep_job_state.job)
                    job_state.readiness_inhibitor_list.append(inhibitor)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


class SessionStateEncoder(json.JSONEncoder):

    _class_indentifiers = {
        JobDefinition: 'JOB_DEFINITION',
        JobResult: 'JOB_RESULT',
        JobState: 'JOB_STATE',
        SessionState: 'SESSION_STATE',
    }

    def default(self, obj):
        """
        JSON Serialize helper to encode SessionState attributes
        Convert objects to a dictionary of their representation
        """
        if (isinstance(obj, (JobDefinition, JobResult, JobState,
                             SessionState))):
            d = {'_class_id': self._class_indentifiers[obj.__class__]}
            d.update(obj._get_persistance_subset())
            return d
        else:
            return json.JSONEncoder.default(self, obj)

    def dict_to_object(self, d):
        """
        JSON Decoder helper
        Convert dictionary to python objects
        """
        if '_class_id' in d:
            for c, id in self._class_indentifiers.items():
                if id == d['_class_id']:
                    cls = c
                    inst = cls.from_json_record(d)
                    break
        else:
            inst = d
        return inst
