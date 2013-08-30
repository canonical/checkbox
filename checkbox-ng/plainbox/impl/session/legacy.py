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
:mod:`plainbox.impl.session.legacy` -- Legacy suspend/resume API
================================================================
"""

import abc
import json
import logging
import os
import shutil
import tempfile

from plainbox.abc import IJobResult
from plainbox.impl.job import JobDefinition
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.jobs import JobState
from plainbox.impl.session.state import SessionState
from plainbox.impl.session.manager import SessionManager
from plainbox.impl.session.storage import SessionStorageRepository

logger = logging.getLogger("plainbox.session.legacy")


class ISessionStateLegacyAPI(metaclass=abc.ABCMeta):
    """
    Interface describing legacy parts of the SessionState API.
    """

    session_data_filename = 'session.json'

    @abc.abstractproperty
    def session_dir(self):
        """
        pathname of a temporary directory for this session

        This is not None only between calls to open() / close().
        """

    @abc.abstractproperty
    def jobs_io_log_dir(self):
        """
        pathname of the jobs IO logs directory

        This is not None only between calls to open() / close().
        """

    @abc.abstractproperty
    def open(self):
        """
        Open session state for running jobs.

        This function creates the cache directory where jobs can store their
        data. See:
        http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
        """

    @abc.abstractmethod
    def clean(self):
        """
        Clean the session directory.
        """

    @abc.abstractmethod
    def previous_session_file(self):
        """
        Check the filesystem for previous session data
        Returns the full pathname to the session file if it exists
        """

    @abc.abstractmethod
    def persistent_save(self):
        """
        Save to disk the minimum needed to resume plainbox where it stopped
        """

    @abc.abstractmethod
    def resume(self):
        """
        Erase the job_state_map and desired_job_list with the saved ones
        """

    @abc.abstractmethod
    def __enter__(self):
        return self

    @abc.abstractmethod
    def __exit__(self, *args):
        self.close()


class SessionStateLegacyAPIOriginalImpl(SessionState, ISessionStateLegacyAPI):
    """
    Original implementation of the legacy suspend/resume API

    This subclass of SessionState implements the ISessionStateLegacyAPI
    interface thus allowing applications to keep using suspend/resume as they
    did before, without adjusting their code.
    """

    session_data_filename = 'session.json'

    def __init__(self, job_list):
        super(SessionStateLegacyAPIOriginalImpl, self).__init__(job_list)
        # Temporary directory used as 'scratch space' for running jobs. Removed
        # entirely when session is terminated. Internally this is exposed as
        # $CHECKBOX_DATA to script environment.
        self._session_dir = None
        # Directory used to store jobs IO logs.
        self._jobs_io_log_dir = None

    @property
    def session_dir(self):
        return self._session_dir

    @property
    def jobs_io_log_dir(self):
        return self._jobs_io_log_dir

    def open(self):
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
        if self._session_dir is not None:
            shutil.rmtree(self._session_dir)
            self._session_dir = None
            self._jobs_io_log_dir = None
            self.open()

    def close(self):
        self._session_dir = None
        self._jobs_io_log_dir = None

    def previous_session_file(self):
        session_filename = os.path.join(self._session_dir,
                                        self.session_data_filename)
        if os.path.exists(session_filename):
            return session_filename
        else:
            return None

    def persistent_save(self):
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


class SessionStateEncoder(json.JSONEncoder):

    _CLS_MAP = {
        DiskJobResult: 'JOB_RESULT(d)',
        JobDefinition: 'JOB_DEFINITION',
        JobState: 'JOB_STATE',
        MemoryJobResult: 'JOB_RESULT(m)',
        SessionStateLegacyAPIOriginalImpl: 'SESSION_STATE',
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


class SessionStateLegacyAPICompatImpl(SessionState, ISessionStateLegacyAPI):
    """
    Compatibility wrapper to use new suspend/resume implementation via the
    original (legacy) suspend/resume API.

    This subclass of SessionState implements the ISessionStateLegacyAPI
    interface thus allowing applications to keep using suspend/resume as they
    did before, without adjusting their code.

    :ivar _manager:
        Instance of SessionManager (this is a bit insane because
        the manager actually knows about the session too)

    :ivar _commit_hint:
        Either None or a set of flags (strings) that determine what kind of
        actions should take place before the next time the 'manager' property
        gets accessed. This is used to implement lazy decision on how to
        map the open/resume/clean methods onto the SessionManager API
    """

    def __init__(self, job_list):
        super(SessionStateLegacyAPICompatImpl, self).__init__(job_list)
        self._manager = None
        self._commit_hint = None

    def open(self):
        """
        Open session state for running jobs.
        """
        logger.debug("SessionState.open()")
        self._add_hint('open')
        return self

    def resume(self):
        """
        Erase the job_state_map and desired_job_list with the saved ones
        """
        logger.debug("SessionState.resume()")
        self._add_hint('resume')
        self._commit_manager()

    def clean(self):
        """
        Clean the session directory.
        """
        logger.debug("SessionState.clean()")
        self._add_hint('clean')
        self._commit_manager()

    def close(self):
        """
        Close the session.

        Legacy API, this function does absolutely nothing
        """
        logger.debug("SessionState.close()")
        self._manager = None
        self._commit_hint = None

    def _add_hint(self, hint):
        if self._commit_hint is None:
            self._commit_hint = set()
        self._commit_hint.add(hint)

    @property
    def manager(self):
        logger.debug(".manager accessed")
        if self._commit_hint is not None:
            self._commit_manager()
        if self._manager is None:
            raise AttributeError("Session not ready, did you call open()?")
        return self._manager

    def _commit_manager(self):
        """
        Commit the new value of the '_manager' instance attribute.

        This method looks at '_commit_hint' to figure out if the semantics
        of open(), resume() or clean() should be applied on the SessionManager
        instance that this class is tracking.
        """
        logger.debug("_commit_manager(), _commit_hint: %r", self._commit_hint)
        assert isinstance(self._commit_hint, set)
        if 'open' in self._commit_hint:
            if 'resume' in self._commit_hint:
                self._commit_resume()
            elif 'clean' in self._commit_hint:
                self._commit_clean()
            else:
                self._commit_open()
        self._commit_hint = None

    def _commit_open(self):
        logger.debug("_commit_open()")
        self._manager = SessionManager.create_session(
            self.job_list, legacy_mode=True)
        # Compatibility hack. Since session manager is supposed to
        # create and manage both session state and session storage
        # we need to inject ourselves into its internal attribute.
        # This way it will keep operating on this instance in the
        # essential checkpoint() method.
        self._manager._state = self

    def _commit_clean(self):
        logger.debug("_commit_clean()")
        if self._manager:
            self._manager.destroy()
            self._manager.create_session(self.job_list)
        self._manager = SessionManager.create_session(
            self.job_list, legacy_mode=True)
        self._manager._state = self

    def _commit_resume(self):
        logger.debug("_commit_resume()")
        last_storage = SessionStorageRepository().get_last_storage()
        assert last_storage is not None, "no saved session to resume"
        self._manager = SessionManager.load_session(
            self.job_list, last_storage)
        # Copy over the resumed state to this instance
        self._job_list = self._manager.state._job_list
        self._job_state_map = self._manager.state._job_state_map
        self._run_list = self._manager.state._run_list
        self._desired_job_list = self._manager.state._desired_job_list
        self._resource_map = self._manager.state._resource_map
        self._metadata = self._manager.state._metadata
        # Copy this instance over what the manager manages
        self._manager._state = self

    @property
    def session_dir(self):
        """
        pathname of a temporary directory for this session

        This is not None only between calls to open() / close().
        """
        return self.manager.storage.location

    @property
    def jobs_io_log_dir(self):
        """
        pathname of the jobs IO logs directory

        This is not None only between calls to open() / close().
        """
        # TODO: use well-known dir helper
        return os.path.join(self.manager.storage.location, 'io-logs')

    def previous_session_file(self):
        """
        Check the filesystem for previous session data
        Returns the full pathname to the session file if it exists
        """
        last_storage = SessionStorageRepository().get_last_storage()
        if last_storage:
            return last_storage.location
        else:
            return None

    def persistent_save(self):
        """
        Save to disk the minimum needed to resume plainbox where it stopped
        """
        self.manager.checkpoint()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


SessionStateLegacyAPI = SessionStateLegacyAPIOriginalImpl
