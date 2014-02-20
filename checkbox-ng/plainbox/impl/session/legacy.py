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
:mod:`plainbox.impl.session.legacy` -- Legacy suspend/resume API
================================================================
"""

import abc
import logging
import os

from plainbox.i18n import gettext as _
from plainbox.impl.session.manager import SessionManager
from plainbox.impl.session.state import SessionState
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
    def remove(self):
        """
        Remove this session
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

    def remove(self):
        logger.debug("SessionState.remove()")
        self.manager.destroy()
        self._manager = None
        self._commit_hint = None

    def _add_hint(self, hint):
        if self._commit_hint is None:
            self._commit_hint = set()
        self._commit_hint.add(hint)

    @property
    def manager(self):
        logger.debug(_(".manager accessed"))
        if self._commit_hint is not None:
            self._commit_manager()
        if self._manager is None:
            raise AttributeError(_("Session not ready, did you call open()?"))
        return self._manager

    def _commit_manager(self):
        """
        Commit the new value of the '_manager' instance attribute.

        This method looks at '_commit_hint' to figure out if the semantics
        of open(), resume() or clean() should be applied on the SessionManager
        instance that this class is tracking.
        """
        logger.debug(
            "_commit_manager(), _commit_hint: %r", self._commit_hint)
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
            self.job_list, last_storage, lambda session: self)
        logger.debug(_("_commit_resume() finished"))

    @property
    def session_dir(self):
        """
        pathname of a temporary directory for this session

        This is not None only between calls to open() / close().
        """
        if self._commit_hint is not None:
            self._commit_manager()
        if self._manager is None:
            return None
        else:
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
        if last_storage and os.path.exists(last_storage.session_file):
            return last_storage.session_file

    def persistent_save(self):
        """
        Save to disk the minimum needed to resume plainbox where it stopped
        """
        self.manager.checkpoint()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


SessionStateLegacyAPI = SessionStateLegacyAPICompatImpl
