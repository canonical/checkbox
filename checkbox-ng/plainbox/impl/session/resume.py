# This file is part of Checkbox.
#
# Copyright 2012, 2013, 2014 Canonical Ltd.
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
from plainbox.i18n import gettext as _
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.secure.qualifiers import SimpleQualifier
from plainbox.impl.session.state import SessionMetaData
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


class EnvelopeUnpackMixIn:
    """
    A mix-in class capable of unpacking the envelope of the session storage
    """

    def unpack_envelope(self, data):
        """
        Unpack the binary envelope and get access to a JSON object

        :param data:
            Bytes representing the dormant session
        :returns:
            the JSON representation of a session stored in the envelope
        :raises CorruptedSessionError:
            if the representation of the session is corrupted in any way
        """
        try:
            data = gzip.decompress(data)
        except IOError:
            raise CorruptedSessionError(_("Cannot decompress session data"))
        try:
            text = data.decode("UTF-8")
        except UnicodeDecodeError:
            raise CorruptedSessionError(_("Cannot decode session text"))
        try:
            return json.loads(text)
        except ValueError:
            raise CorruptedSessionError(_("Cannot interpret session JSON"))


class SessionPeekHelper(EnvelopeUnpackMixIn):

    def peek(self, data):
        """
        Peek at the meta-data of a dormant session.

        :param data:
            Bytes representing the dormant session
        :returns:
            a SessionMetaData object
        :raises CorruptedSessionError:
            if the representation of the session is corrupted in any way
        :raises IncompatibleSessionError:
            if session serialization format is not supported
        """
        json_repr = self.unpack_envelope(data)
        return self._peek_json(json_repr)

    def _peek_json(self, json_repr):
        """
        Resume a SessionMetaData object from the JSON representation.

        This method is called by :meth:`peek()` after the initial envelope
        and parsing is done. The only error conditions that can happen
        are related to semantic incompatibilities or corrupted internal state.
        """
        logger.debug(_("Peeking at json... (see below)"))
        logger.debug(json.dumps(json_repr, indent=4))
        _validate(json_repr, value_type=dict)
        version = _validate(json_repr, key="version", choice=[1])
        if version == 1:
            return SessionPeekHelper1().peek_json(json_repr)
        elif version == 2:
            return SessionPeekHelper2().peek_json(json_repr)
        elif version == 3:
            return SessionPeekHelper3().peek_json(json_repr)
        else:
            raise IncompatibleSessionError(
                _("Unsupported version {}").format(version))


class SessionResumeHelper(EnvelopeUnpackMixIn):
    """
    Helper class for implementing session resume feature.

    This class is a facade that does enough of the resume process to know which
    version is being resumed and delegate the rest of the process to an
    appropriate, format specific, resume class.
    """

    def __init__(self, job_list):
        """
        Initialize the helper with a list of known jobs.
        """
        self.job_list = job_list

    def resume(self, data, early_cb=None):
        """
        Resume a dormant session.

        :param data:
            Bytes representing the dormant session
        :param early_cb:
            A callback that allows the caller to "see" the session object
            early, before the bulk of resume operation happens. This method can
            be used to register signal listeners on the new session before this
            method call returns. The callback accepts one argument, session,
            which is being resumed.
        :returns:
            resumed session instance
        :rtype:
            :class:`~plainbox.impl.session.state.SessionState`

        This method validates the representation of a dormant session and
        re-creates an identical SessionState instance. It can fail in multiple
        ways, some of which are a part of normal operation and should always be
        handled (:class:`IncompatibleJobError` and
        :class:`IncompatibleJobError`). Applications may wish to capture
        :class:`SessionResumeError` as a generic base exception for all the
        possible problems.

        :raises CorruptedSessionError:
            if the representation of the session is corrupted in any way
        :raises IncompatibleSessionError:
            if session serialization format is not supported
        :raises IncompatibleJobError:
            if serialized jobs are not the same as current jobs
        """
        json_repr = self.unpack_envelope(data)
        return self._resume_json(json_repr, early_cb)

    def _resume_json(self, json_repr, early_cb=None):
        """
        Resume a SessionState object from the JSON representation.

        This method is called by :meth:`resume()` after the initial envelope
        and parsing is done. The only error conditions that can happen
        are related to semantic incompatibilities or corrupted internal state.
        """
        logger.debug(_("Resuming from json... (see below)"))
        logger.debug(json.dumps(json_repr, indent=4))
        _validate(json_repr, value_type=dict)
        version = _validate(json_repr, key="version", choice=[1])
        if version == 1:
            return SessionResumeHelper1(
                self.job_list).resume_json(json_repr, early_cb)
        elif version == 2:
            return SessionResumeHelper2(
                self.job_list).resume_json(json_repr, early_cb)
        elif version == 3:
            return SessionResumeHelper3(
                self.job_list).resume_json(json_repr, early_cb)
        else:
            raise IncompatibleSessionError(
                _("Unsupported version {}").format(version))


class ResumeDiscardQualifier(SimpleQualifier):
    """
    A job qualifier that designates jobs that should be removed
    after doing a session resume.
    """

    def __init__(self, jobs_repr):
        super().__init__()
        # Set of ids of jobs to retain (computed as keys of the
        # dictionary taken from the session resume representation)
        self._retain_id_set = frozenset(jobs_repr)

    def get_simple_match(self, job):
        return job.id not in self._retain_id_set


class MetaDataHelper1MixIn:

    @classmethod
    def _restore_SessionState_metadata(cls, metadata, session_repr):
        """
        Extract meta-data information from the representation of the session
        and set it in the given session object
        """
        # Get the representation of the meta-data
        metadata_repr = _validate(
            session_repr, key='metadata', value_type=dict)
        # Set each bit back to the session
        metadata.title = _validate(
            metadata_repr, key='title', value_type=str, value_none=True)
        metadata.flags = set([
            _validate(
                flag, value_type=str,
                value_type_msg=_("Each flag must be a string"))
            for flag in _validate(
                metadata_repr, key='flags', value_type=list)])
        metadata.running_job_name = _validate(
            metadata_repr, key='running_job_name', value_type=str,
            value_none=True)


class MetaDataHelper2MixIn(MetaDataHelper1MixIn):

    @classmethod
    def _restore_SessionState_metadata(cls, metadata, session_repr):
        """
        Extract meta-data information from the representation of the session
        and set it in the given session object
        """
        super()._restore_SessionState_metadata(metadata, session_repr)
        # Get the representation of the meta-data
        metadata_repr = _validate(
            session_repr, key='metadata', value_type=dict)
        app_blob = _validate(
            metadata_repr, key='app_blob', value_type=str,
            value_none=True)
        if app_blob is not None:
            try:
                app_blob = app_blob.encode("ASCII")
            except UnicodeEncodeError:
                # TRANSLATORS: please don't translate app_blob
                raise CorruptedSessionError(_("app_blob is not ASCII"))
            try:
                app_blob = base64.standard_b64decode(app_blob)
            except binascii.Error:
                # TRANSLATORS: please don't translate app_blob
                raise CorruptedSessionError(_("Cannot base64 decode app_blob"))
        metadata.app_blob = app_blob


class MetaDataHelper3MixIn(MetaDataHelper2MixIn):

    @classmethod
    def _restore_SessionState_metadata(cls, metadata, session_repr):
        """
        Extract meta-data information from the representation of the session
        and set it in the given session object
        """
        super()._restore_SessionState_metadata(metadata, session_repr)
        # Get the representation of the meta-data
        metadata_repr = _validate(
            session_repr, key='metadata', value_type=dict)
        metadata.app_id = _validate(
            metadata_repr, key='app_id', value_type=str,
            value_none=True)


class SessionPeekHelper1(MetaDataHelper1MixIn):
    """
    Helper class for implementing session peek feature

    This class works with data constructed by
    :class:`~plainbox.impl.session.suspend.SessionSuspendHelper1` which has
    been pre-processed by :class:`SessionPeekHelper` (to strip the initial
    envelope).

    The only goal of this class is to reconstruct session state meta-data.
    """

    def peek_json(self, json_repr):
        """
        Resume a SessionState object from the JSON representation.

        This method is called by :meth:`peek()` after the initial envelope and
        parsing is done. The only error conditions that can happen are related
        to semantic incompatibilities or corrupted internal state.
        """
        _validate(json_repr, key="version", choice=[1])
        session_repr = _validate(json_repr, key='session', value_type=dict)
        metadata = SessionMetaData()
        self._restore_SessionState_metadata(metadata, session_repr)
        return metadata

    def _build_SessionState(self, session_repr, early_cb=None):
        """
        Reconstruct the session state object.

        This method creates a fresh SessionState instance and restores
        jobs, results, meta-data and desired job list using helper methods.
        """
        logger.debug(_("Starting to restore metadata..."))
        metadata = SessionMetaData()
        self._peek_SessionState_metadata(metadata, session_repr)
        return metadata


class SessionPeekHelper2(MetaDataHelper2MixIn, SessionPeekHelper1):
    """
    Helper class for implementing session peek feature

    This class works with data constructed by
    :class:`~plainbox.impl.session.suspend.SessionSuspendHelper1` which has
    been pre-processed by :class:`SessionPeekHelper` (to strip the initial
    envelope).

    The only goal of this class is to reconstruct session state meta-data.
    """


class SessionPeekHelper3(MetaDataHelper3MixIn, SessionPeekHelper2):
    """
    Helper class for implementing session peek feature

    This class works with data constructed by
    :class:`~plainbox.impl.session.suspend.SessionSuspendHelper1` which has
    been pre-processed by :class:`SessionPeekHelper` (to strip the initial
    envelope).

    The only goal of this class is to reconstruct session state meta-data.
    """


class SessionResumeHelper1(MetaDataHelper1MixIn):
    """
    Helper class for implementing session resume feature

    This class works with data constructed by
    :class:`~plainbox.impl.session.suspend.SessionSuspendHelper1` which has
    been pre-processed by :class:`SessionResumeHelper` (to strip the initial
    envelope).

    Due to the constraints of what can be represented in a suspended session,
    this class cannot work in isolation. It must operate with a list of know
    jobs.

    Since (most of the) jobs are being provided externally (as they represent
    the non-serialized parts of checkbox or other job providers) several
    failure modes are possible. Those are documented in :meth:`resume()`
    """

    def __init__(self, job_list):
        """
        Initialize the helper with a list of known jobs.
        """
        self.job_list = job_list

    def resume_json(self, json_repr, early_cb=None):
        """
        Resume a SessionState object from the JSON representation.

        This method is called by :meth:`resume()` after the initial envelope
        and parsing is done. The only error conditions that can happen
        are related to semantic incompatibilities or corrupted internal state.
        """
        _validate(json_repr, key="version", choice=[1])
        session_repr = _validate(json_repr, key='session', value_type=dict)
        return self._build_SessionState(session_repr, early_cb)

    def _build_SessionState(self, session_repr, early_cb=None):
        """
        Reconstruct the session state object.

        This method creates a fresh SessionState instance and restores
        jobs, results, meta-data and desired job list using helper methods.
        """
        # Construct a fresh session object.
        session = SessionState(self.job_list)
        logger.debug(_("Constructed new session for resume %r"), session)
        # Give early_cb a chance to see the session before we start resuming.
        # This way applications can see, among other things, generated jobs
        # as they are added to the session, by registering appropriate signal
        # handlers on the freshly-constructed session instance.
        if early_cb is not None:
            logger.debug(_("Invoking early callback %r"), early_cb)
            new_session = early_cb(session)
            if new_session is not None:
                logger.debug(
                    _("Using different session for resume: %r"), new_session)
                session = new_session
        # Restore bits and pieces of state
        logger.debug(
            _("Starting to restore jobs and results to %r..."), session)
        self._restore_SessionState_jobs_and_results(session, session_repr)
        logger.debug(_("Starting to restore metadata..."))
        self._restore_SessionState_metadata(session.metadata, session_repr)
        logger.debug(_("restored metadata %r"), session.metadata)
        logger.debug(_("Starting to restore desired job list..."))
        self._restore_SessionState_desired_job_list(session, session_repr)
        logger.debug(_("Starting to restore job list..."))
        self._restore_SessionState_job_list(session, session_repr)
        # Return whatever we've got
        logger.debug(_("Resume complete!"))
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
        # List of jobs (ids) that could not be processed on the first pass
        leftover_jobs = deque()
        # Run a first pass through jobs and results. Anything that didn't
        # work (generated jobs) gets added to leftover_jobs list.
        # To make this bit deterministic (we like determinism) we're always
        # going to process job results in alphabetic orderer.
        first_pass_list = sorted(
            set(jobs_repr.keys()) | set(results_repr.keys()))
        for job_id in first_pass_list:
            try:
                self._process_job(session, jobs_repr, results_repr, job_id)
            except KeyError:
                leftover_jobs.append(job_id)
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
                job_id = leftover_jobs.popleft()
                # Treat the sentinel None object as the end of the iteration
                if job_id is None:
                    break
                try:
                    self._process_job(
                        session, jobs_repr, results_repr, job_id)
                except KeyError:
                    leftover_jobs.append(job_id)
                else:
                    leftover_shrunk = True
            # Check if we're making any progress.
            # We don't want to keep spinning on a list of some bogus jobs
            # that nothing generated so we need an end condition for that case
            if not leftover_shrunk:
                raise CorruptedSessionError(
                    _("Unknown jobs remaining: {}").format(
                        ", ".join(leftover_jobs)))

    def _process_job(self, session, jobs_repr, results_repr, job_id):
        """
        Process all representation details associated with a particular job

        This method takes a session object, representation of all the jobs
        and all the results (and a job id) and tries to reconstruct the
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
        _validate(job_id, value_type=str)
        # Get the checksum from the representation
        checksum = _validate(
            jobs_repr, key=job_id, value_type=str)
        # Look up the actual job definition in the session.
        # This can raise KeyError but it is okay, callers expect that
        job = session.job_state_map[job_id].job
        # Check if job definition has not changed
        if job.checksum != checksum:
            raise IncompatibleJobError(
                _("Definition of job {!r} has changed").format(job_id))
        # Collect all of the result objects into result_list
        result_list = []
        result_list_repr = _validate(
            results_repr, key=job_id, value_type=list, value_none=True)
        for result_repr in result_list_repr:
            _validate(result_repr, value_type=dict)
            result = self._build_JobResult(result_repr)
            result_list.append(result)
        # Show the _LAST_ result to the session. Currently we only store one
        # result but showing the most recent (last) result should be good
        # in general.
        if len(result_list) > 0:
            logger.debug(
                _("calling update_job_result(%r, %r)"), job, result_list[-1])
            session.update_job_result(job, result_list[-1])

    @classmethod
    def _restore_SessionState_desired_job_list(cls, session, session_repr):
        """
        Extract the representation of desired_job_list from the session and
        set it back to the session object. This method should be called after
        all the jobs are discovered.

        :raises CorruptedSessionError:
            if desired_job_list refers to unknown job
        """
        # List of all the _ids_ of the jobs that were selected
        desired_job_list = [
            _validate(
                job_id, value_type=str,
                value_type_msg=_("Each job id must be a string"))
            for job_id in _validate(
                session_repr, key='desired_job_list', value_type=list)]
        # Restore job selection
        logger.debug(
            _("calling update_desired_job_list(%r)"), desired_job_list)
        try:
            session.update_desired_job_list([
                session.job_state_map[job_id].job
                for job_id in desired_job_list])
        except KeyError as exc:
            raise CorruptedSessionError(
                _("'desired_job_list' refers to unknown job {!r}").format(
                    exc.args[0]))

    @classmethod
    def _restore_SessionState_job_list(cls, session, session_repr):
        """
        Trim job_list so that it has only those jobs that are mentioned by the
        session representation. This should never fail as anything that might
        go wrong must have gone wrong before.
        """

        # Representation of all of the job definitions
        jobs_repr = _validate(session_repr, key='jobs', value_type=dict)
        # Qualifier ready to select jobs to remove
        qualifier = ResumeDiscardQualifier(jobs_repr)
        # NOTE: this should never raise ValueError (which signals that we
        # tried to remove a job which is in the run list) because it should
        # only remove jobs that were not in the representation and any job in
        # the run list must be in the representation already.
        session.trim_job_list(qualifier)

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
            # TRANSLATORS: please keep delay untranslated
            raise CorruptedSessionError(_("delay cannot be negative"))
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
                _("record data {!r} is not ASCII").format(data))
        try:
            data = base64.standard_b64decode(data)
        except binascii.Error:
            raise CorruptedSessionError(
                _("record data {!r} is not correct base64").format(data))
        return IOLogRecord(delay, stream_name, data)


class SessionResumeHelper2(MetaDataHelper2MixIn, SessionResumeHelper1):
    """
    Helper class for implementing session resume feature

    This class works with data constructed by
    :class:`~plainbox.impl.session.suspend.SessionSuspendHelper2` which has
    been pre-processed by :class:`SessionResumeHelper` (to strip the initial
    envelope).

    Due to the constraints of what can be represented in a suspended session,
    this class cannot work in isolation. It must operate with a list of know
    jobs.

    Since (most of the) jobs are being provided externally (as they represent
    the non-serialized parts of checkbox or other job providers) several
    failure modes are possible. Those are documented in :meth:`resume()`
    """


class SessionResumeHelper3(MetaDataHelper3MixIn, SessionResumeHelper2):
    """
    Helper class for implementing session resume feature

    This class works with data constructed by
    :class:`~plainbox.impl.session.suspend.SessionSuspendHelper3` which has
    been pre-processed by :class:`SessionResumeHelper` (to strip the initial
    envelope).

    Due to the constraints of what can be represented in a suspended session,
    this class cannot work in isolation. It must operate with a list of know
    jobs.

    Since (most of the) jobs are being provided externally (as they represent
    the non-serialized parts of checkbox or other job providers) several
    failure modes are possible. Those are documented in :meth:`resume()`
    """


def _validate(obj, **flags):
    """
    Multi-purpose extraction and validation function.
    """
    # Fetch data from the container OR use json_repr directly
    if 'key' in flags:
        key = flags['key']
        obj_name = _("key {!r}").format(key)
        try:
            value = obj[key]
        except (TypeError, IndexError, KeyError):
            error_msg = flags.get(
                "missing_key_msg",
                _("Missing value for key {!r}").format(key))
            raise CorruptedSessionError(error_msg)
    else:
        value = obj
        obj_name = _("object")
    # Check if value can be None (defaulting to "no")
    value_none = flags.get('value_none', False)
    if value is None and value_none is False:
        error_msg = flags.get(
            "value_none_msg",
            _("Value of {} cannot be None").format(obj_name))
        raise CorruptedSessionError(error_msg)
    # Check if value is of correct type
    if value is not None and "value_type" in flags:
        value_type = flags['value_type']
        if not isinstance(value, value_type):
            error_msg = flags.get(
                "value_type_msg",
                _("Value of {} is of incorrect type {}").format(
                    obj_name, type(value).__name__))
            raise CorruptedSessionError(error_msg)
    # Check if value is in the set of correct values
    if "value_choice" in flags:
        value_choice = flags['value_choice']
        if value not in value_choice:
            error_msg = flags.get(
                "value_choice_msg",
                _("Value for {} not in allowed set {!r}").format(
                    obj_name, value_choice))
            raise CorruptedSessionError(error_msg)
    return value
