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
:mod:`plainbox.impl.session.resume` -- session resume handling
==============================================================

This module contains classes that can resume a dormant session from
a binary representation. See docs for the suspend module for details.

The resume logic provides a compromise between usefulness and correctness
so two assumptions are made:

* We assume that a checksum of a job changes when their behavior changes.
  This way we can detect when job definitions were updated after
  suspending but before resuming.

* We assume that software and hardware *may* change while the session is
  suspended but this is not something that framework (PlainBox) is
  concerned with. Applications should provide job definitions that
  are capable of detecting this and acting appropriately.

  This is true since the user may install additional packages
  or upgrade existing packages. The user can also add or remove pluggable
  hardware. Lastly actual machine suspend (or hibernate) and resume *may*
  cause alterations to the hardware as it is visible from within
  the system. In any case the framework does not care about this.
"""

from collections import deque
import base64
import binascii
import gzip
import json
import logging

from plainbox.abc import IJobResult
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.session.state import SessionState

logger = logging.getLogger("plainbox.session.resume")


class SessionResumeError(Exception):
    """
    Base class for exceptions that can be raised when attempting to
    resume a dormant session.
    """


class CorruptedSessionError(SessionResumeError):
    """
    Exception raised when :class:`SessionResumeHelper` cannot decode
    the session byte stream. This exception will be raised with additional
    context that captures the actual underlying cause. Having this exception
    class makes it easier to handle resume errors.
    """


class IncompatibleSessionError(SessionResumeError):
    """
    Exception raised when :class:`SessionResumeHelper` comes across malformed
    or unsupported data that was (presumably) produced by
    :class:`SessionSuspendHelper`
    """


class IncompatibleJobError(SessionResumeError):
    """
    Exception raised when :class:`SessionResumeHelper` detects that the set of
    jobs it knows about is incompatible with what was saved before.
    """


class SessionResumeHelper:
    """
    Helper class for implementing session resume feature

    This class works with data constructed by
    :class:`~plainbox.impl.session.suspend.SessionSuspendHelper`.

    Due to the constraints of what can be represented in a suspended session,
    this class cannot work in isolation. It must operate with a list of
    know jobs.

    Since (most of the) jobs are being provided externally (as they represent
    the non-serialized parts of checkbox or other job providers) several
    failure modes are possible. Those are documented in :meth:`resume()`
    """

    def __init__(self, job_list):
        """
        Initialize the helper with a list of known jobs.
        """
        self.job_list = job_list

    def resume(self, data):
        """
        Resume a dormant session.

        :param data:
            bytes representing the dormant session

        :returns:
            resumed session instance
        :rtype:
            :class:`~plainbox.impl.session.state.SessionState`

        This method validates the representation of a dormant session and
        re-creates a similar-but-not-identical SessionState instance.
        It can fail in multiple ways, some of which are a part of normal
        operation and should always be handled (:class:`IncompatibleJobError`
        and :class:`IncompatibleJobError`). Applications may wish to capture
        :class:`SessionResumeError` as a generic base exception for all
        the possible problems.

        :raises CorruptedSessionError:
            if the representation of the session is corrupted in any way
        :raises IncompatibleSessionError:
            if session serialization format is not supported
        :raises IncompatibleJobError:
            if serialized jobs are not the same as current jobs
        """
        try:
            data = gzip.decompress(data)
        except IOError:
            raise CorruptedSessionError("Cannot decompress session data")
        try:
            text = data.decode("UTF-8")
        except UnicodeDecodeError:
            raise CorruptedSessionError("Cannot decode session text")
        try:
            json_repr = json.loads(text)
        except ValueError:
            raise CorruptedSessionError("Cannot interpret session JSON")
        return self._resume_json(json_repr)

    def _resume_json(self, json_repr):
        """
        Resume a SessionState object from the JSON representation.

        This method is called by :meth:`resume()` after the initial envelope
        and parsing is done. The only error conditions that can happen
        are related to semantic incompatibilities or corrupted internal state.
        """
        logger.debug("Resuming from json... (see below)")
        logger.debug(json.dumps(json_repr, indent=4))
        _validate(json_repr, value_type=dict)
        _validate(json_repr, key="version", choice=[1])
        session_repr = _validate(json_repr, key='session', value_type=dict)
        return self._build_SessionState(session_repr)

    def _build_SessionState(self, session_repr):
        """
        Reconstruct the session state object.

        This method creates a fresh SessionState instance and restores
        jobs, results, meta-data and desired job list using helper methods.
        """
        # Construct a fresh session object.
        session = SessionState(self.job_list)
        # Restore bits and pieces of state
        self._restore_SessionState_jobs_and_results(session, session_repr)
        self._restore_SessionState_metadata(session, session_repr)
        self._restore_SessionState_desired_job_list(session, session_repr)
        # Return whatever we've got
        return session

    def _restore_SessionState_jobs_and_results(self, session, session_repr):
        """
        Process representation of a session and restore jobs and results.

        This method reconstructs all jobs and results in several stages.
        The first pass just goes over all the jobs and results and restores
        all of the non-generated jobs using :meth:`_process_job()` method.
        Any jobs that cannot be processed (generated job) is saved for further
        processing.
        """
        # Representation of all of the job definitions
        jobs_repr = _validate(session_repr, key='jobs', value_type=dict)
        # Representation of all of the job results
        results_repr = _validate(session_repr, key='results', value_type=dict)
        # List of jobs (names) that could not be processed on the first pass
        leftover_jobs = deque()
        # Run a first pass through jobs and results. Anything that didn't
        # work (generated jobs) gets added to leftover_jobs list.
        # To make this bit deterministic (we like determinism) we're always
        # going to process job results in alphabetic orderer.
        first_pass_list = sorted(
            set(jobs_repr.keys()) | set(results_repr.keys()))
        for job_name in first_pass_list:
            try:
                self._process_job(session, jobs_repr, results_repr, job_name)
            except KeyError:
                leftover_jobs.append(job_name)
        # Process leftovers. For each iteration the leftover_jobs list should
        # shrink or we're not making any progress. If that happens we've got
        # undefined jobs (in general the session is corrupted)
        while leftover_jobs:
            # Append a sentinel object so that we can know when we're
            # done "iterating" over the collection once.
            # Also: https://twitter.com/zygoon/status/370213046678872065
            leftover_jobs.append(None)
            leftover_shrunk = False
            while leftover_jobs:  # pragma: no branch
                job_name = leftover_jobs.popleft()
                # Treat the sentinel None object as the end of the iteration
                if job_name is None:
                    break
                try:
                    self._process_job(
                        session, jobs_repr, results_repr, job_name)
                except KeyError:
                    leftover_jobs.append(job_name)
                else:
                    leftover_shrunk = True
            # Check if we're making any progress.
            # We don't want to keep spinning on a list of some bogus jobs
            # that nothing generated so we need an end condition for that case
            if not leftover_shrunk:
                raise CorruptedSessionError(
                    "Unknown jobs remaining: {}".format(
                        ", ".join(leftover_jobs)))

    def _process_job(self, session, jobs_repr, results_repr, job_name):
        """
        Process all representation details associated with a particular job

        This method takes a session object, representation of all the jobs
        and all the results (and a job name) and tries to reconstruct the
        state associated with that job in the session object.

        Jobs are verified to match existing (known) jobs. Results are
        rebuilt from their representation and presented back to the session
        for processing (this restores resources and generated jobs).

        This method can fail in normal operation, when the job that was
        being processed is a generated job and has not been reintroduced into
        the session. When that happens a KeyError is raised.

        .. note::
            Since the representation format for results can support storing
            and restoring a list of results (per job) but the SessionState
            cannot yet do that the implementation of this method restores
            the state of the _last_ result object only.
        """
        _validate(job_name, value_type=str)
        # Get the checksum from the representation
        checksum = _validate(
            jobs_repr, key=job_name, value_type=str)
        # Look up the actual job definition in the session.
        # This can raise KeyError but it is okay, callers expect that
        job = session.job_state_map[job_name].job
        # Check if job definition has not changed
        if job.get_checksum() != checksum:
            raise IncompatibleJobError(
                "Definition of job {!r} has changed".format(job_name))
        # Collect all of the result objects into result_list
        result_list = []
        result_list_repr = _validate(
            results_repr, key=job_name, value_type=list, value_none=True)
        for result_repr in result_list_repr:
            _validate(result_repr, value_type=dict)
            result = self._build_JobResult(result_repr)
            result_list.append(result)
        # Show the _LAST_ result to the session. Currently we only store one
        # result but showing the most recent (last) result should be good
        # in general.
        if len(result_list) > 0:
            session.update_job_result(job, result_list[-1])

    @classmethod
    def _restore_SessionState_metadata(cls, session, session_repr):
        """
        Extract meta-data information from the representation of the session
        and set it in the given session object
        """
        # Get the representation of the meta-data
        metadata_repr = _validate(
            session_repr, key='metadata', value_type=dict)
        # Set each bit back to the session
        session.metadata.title = _validate(
            metadata_repr, key='title', value_type=str, value_none=True)
        session.metadata.flags = set([
            _validate(
                flag, value_type=str,
                value_type_msg="Each flag must be a string")
            for flag in _validate(
                metadata_repr, key='flags', value_type=list)])
        session.metadata.running_job_name = _validate(
            metadata_repr, key='running_job_name', value_type=str,
            value_none=True)

    @classmethod
    def _restore_SessionState_desired_job_list(cls, session, session_repr):
        """
        Extract the representation of desired_job_list from the session and
        set it back to the session object. This method should be called after
        all the jobs are discovered.

        :raises CorruptedSessionError:
            if desired_job_list refers to unknown job
        """
        # List of all the _names_ of the jobs that were selected
        desired_job_list = [
            _validate(
                job_name, value_type=str,
                value_type_msg="Each job name must be a string")
            for job_name in _validate(
                session_repr, key='desired_job_list', value_type=list)]
        # Restore job selection
        try:
            session.update_desired_job_list([
                session.job_state_map[job_name].job
                for job_name in desired_job_list])
        except KeyError as exc:
            raise CorruptedSessionError(
                "'desired_job_list' refers to unknown job {!r}".format(
                    exc.args[0]))

    @classmethod
    def _build_JobResult(cls, result_repr):
        """
        Convert the representation of MemoryJobResult or DiskJobResult
        back into an actual instance.
        """
        # Load all common attributes...
        outcome = _validate(
            result_repr, key='outcome', value_type=str,
            value_choice=IJobResult.ALL_OUTCOME_LIST, value_none=True)
        comments = _validate(
            result_repr, key='comments', value_type=str, value_none=True)
        return_code = _validate(
            result_repr, key='return_code', value_type=int, value_none=True)
        execution_duration = _validate(
            result_repr, key='execution_duration', value_type=float,
            value_none=True)
        # Construct either DiskJobResult or MemoryJobResult
        if 'io_log_filename' in result_repr:
            io_log_filename = _validate(
                result_repr, key='io_log_filename', value_type=str)
            return DiskJobResult({
                'outcome': outcome,
                'comments': comments,
                'execution_duration': execution_duration,
                'io_log_filename': io_log_filename,
                'return_code': return_code
            })
        else:
            io_log = [
                cls._build_IOLogRecord(record_repr)
                for record_repr in _validate(
                    result_repr, key='io_log', value_type=list)]
            return MemoryJobResult({
                'outcome': outcome,
                'comments': comments,
                'execution_duration': execution_duration,
                'io_log': io_log,
                'return_code': return_code
            })

    @classmethod
    def _build_IOLogRecord(cls, record_repr):
        """
        Convert the representation of IOLogRecord back the the object
        """
        _validate(record_repr, value_type=list)
        delay = _validate(record_repr, key=0, value_type=float)
        if delay < 0:
            raise CorruptedSessionError("delay cannot be negative")
        stream_name = _validate(
            record_repr, key=1, value_type=str,
            value_choice=['stdout', 'stderr'])
        data = _validate(record_repr, key=2, value_type=str)
        # Each data item is a base64 string created by encoding the bytes and
        # converting them to ASCII. To get the original we need to undo that
        # operation.
        try:
            data = data.encode("ASCII")
        except UnicodeEncodeError:
            raise CorruptedSessionError(
                "record data {!r} is not ASCII", data)
        try:
            data = base64.standard_b64decode(data)
        except binascii.Error:
            raise CorruptedSessionError(
                "record data {!r} is not correct base64")
        return IOLogRecord(delay, stream_name, data)


def _validate(obj, **flags):
    """
    Multi-purpose extraction and validation function.
    """
    # Fetch data from the container OR use json_repr directly
    if 'key' in flags:
        key = flags['key']
        obj_name = "key {!r}".format(key)
        try:
            value = obj[key]
        except (TypeError, IndexError, KeyError):
            error_msg = flags.get(
                "missing_key_msg",
                "Missing value for key {!r}".format(key))
            raise CorruptedSessionError(error_msg)
    else:
        value = obj
        obj_name = "object"
    # Check if value can be None (defaulting to "no")
    value_none = flags.get('value_none', False)
    if value is None and value_none is False:
        error_msg = flags.get(
            "value_none_msg",
            "Value of {} cannot be None".format(obj_name))
        raise CorruptedSessionError(error_msg)
    # Check if value is of correct type
    if value is not None and "value_type" in flags:
        value_type = flags['value_type']
        if not isinstance(value, value_type):
            error_msg = flags.get(
                "value_type_msg",
                "Value of {} is of incorrect type {}".format(
                    obj_name, type(value).__name__))
            raise CorruptedSessionError(error_msg)
    # Check if value is in the set of correct values
    if "value_choice" in flags:
        value_choice = flags['value_choice']
        if value not in value_choice:
            error_msg = flags.get(
                "value_choice_msg",
                "Value for {} not in allowed set {!r}".format(
                    obj_name, value_choice))
            raise CorruptedSessionError(error_msg)
    return value
