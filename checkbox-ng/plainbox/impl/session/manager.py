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
:mod:`plainbox.impl.session.manager` -- manager for sessions
============================================================

This module contains glue code that allows one to create and manage sessions
and their filesystem presence. It allows
:class:`~plainbox.impl.session.state.SessionState` to be de-coupled
from :class:`~plainbox.impl.session.storage.SessionStorageRepository`,
:class:`~plainbox.impl.session.storage.SessionStorage`,
:class:`~plainbox.impl.session.suspend.SessionSuspendHelper`
and :class:`~plainbox.impl.session.suspend.SessionResumeHelper`.
"""

import errno
import logging
import os

from plainbox.i18n import gettext as _
from plainbox.impl.session.resume import SessionResumeHelper
from plainbox.impl.session.state import SessionState
from plainbox.impl.session.storage import LockedStorageError
from plainbox.impl.session.storage import SessionStorage
from plainbox.impl.session.storage import SessionStorageRepository
from plainbox.impl.session.suspend import SessionSuspendHelper

logger = logging.getLogger("plainbox.session.manager")


class WellKnownDirsHelper:
    """
    Helper class that knows about well known directories for SessionStorage.

    This class simply gets rid of various magic directory names that we
    associate with session storage. It also provides a convenience utility
    method :meth:`populate()` to create all of those directories, if needed.
    """

    def __init__(self, storage):
        assert isinstance(storage, SessionStorage)
        self._storage = storage

    @property
    def storage(self):
        """
        :class:`~plainbox.impl.session.storage.SessionStorage` associated with
        this helper
        """
        return self._storage

    def populate(self):
        """
        Create all of the well known directories that are expected to exist
        inside a freshly created session storage directory
        """
        for dirname in self.all_directories:
            if not os.path.exists(dirname):
                os.makedirs(dirname)

    @property
    def all_directories(self):
        """
        a list of all well-known directories
        """
        return [self.io_log_pathname]

    @property
    def io_log_pathname(self):
        """
        full path of the directory where per-job IO logs are stored
        """
        return os.path.join(self.storage.location, "io-logs")


class SessionManager:
    """
    Manager class for coupling SessionStorage with SessionState.

    This class allows application code to manage disk state of sessions. Using
    the :meth:`checkpoint()` method applications can create persistent
    snapshots of the :class:`~plainbox.impl.session.state.SessionState`
    associated with each :class:`SessionManager`.
    """

    def __init__(self, state, storage):
        """
        Initialize a manager with a specific
        :class:`~plainbox.impl.session.state.SessionState` and
        :class:`~plainbox.impl.session.storage.SessionStorage`.
        """
        assert isinstance(state, SessionState)
        assert isinstance(storage, SessionStorage)
        self._state = state
        self._storage = storage
        logger.debug(
            _("Created SessionManager with state:%r and storage:%r"),
            state, storage)

    @property
    def state(self):
        """
        :class:`~plainbox.impl.session.state.SessionState` associated with
        this manager
        """
        return self._state

    @property
    def storage(self):
        """
        :class:`~plainbox.impl.session.storage.SessionStorage` associated with
        this manager
        """
        return self._storage

    @classmethod
    def create_session(cls, job_list=None, repo=None, legacy_mode=False):
        """
        Create a session manager with a fresh session.

        This method populates the session storage with all of the well known
        directories (using :meth:`WellKnownDirsHelper.populate()`)

        :param job_list:
            If specified then this will be the initial list of jobs known
            by the session state object. This can be specified for convenience
            but is really optional since the application can always add more
            jobs to an existing session.
        :ptype job_list:
            list of :class:`~plainbox.abc.IJobDefinition`.
        :param repo:
            If specified then this particular repository will be used to create
            the storage for this session. If left out, a new repository is
            constructed with the default location.
        :ptype repo:
            :class:`~plainbox.impl.session.storage.SessionStorageRepository`.
        :param legacy_mode:
            Propagated to
            :meth:`~plainbox.impl.session.storage.SessionStorage.create()`
            to ensure that legacy (single session) mode is used.
        :ptype legacy_mode:
            bool
        :return:
            fresh :class:`SessionManager` instance
        """
        logger.debug(_("SessionManager.create_session()"))
        if job_list is None:
            job_list = []
        state = SessionState(job_list)
        if repo is None:
            repo = SessionStorageRepository()
        storage = SessionStorage.create(repo.location, legacy_mode)
        WellKnownDirsHelper(storage).populate()
        return cls(state, storage)

    @classmethod
    def load_session(cls, job_list, storage, early_cb=None):
        """
        Load a previously checkpointed session.

        This method allows one to re-open a session that was previously
        created by :meth:`SessionManager.checkpoint()`

        :param job_list:
            List of all known jobs. This argument is used to reconstruct the
            session from a dormant state. Since the suspended data cannot
            capture implementation details of each job reliably actual jobs
            need to be provided externally. Unlike in :meth:`create_session()`
            this list really needs to be complete, it must also include
            any generated jobs.
        :param storage:
            The storage that should be used for this particular session.
            The storage object holds references to existing directories
            in the file system. When restoring an existing dormant session
            it is important to use the correct storage object, the one that
            corresponds to the file system location used be the session
            before it was saved.
        :ptype storage:
            :class:`~plainbox.impl.session.storage.SessionStorage`
        :param early_cb:
            A callback that allows the caller to "see" the session object
            early, before the bulk of resume operation happens. This method can
            be used to register callbacks on the new session before this method
            call returns. The callback accepts one argument, session, which is
            being resumed. This is being passed directly to
            :meth:`plainbox.impl.session.resume.SessionResumeHelper.resume()`
        :raises:
            Anything that can be raised by
            :meth:`~plainbox.impl.session.storage.SessionStorage.
            load_checkpoint()` and :meth:`~plainbox.impl.session.suspend.
            SessionResumeHelper.resume()`
        :returns:
            Fresh instance of :class:`SessionManager`
        """
        logger.debug(_("SessionManager.load_session()"))
        try:
            data = storage.load_checkpoint()
        except IOError as exc:
            if exc.errno == errno.ENOENT:
                state = SessionState(job_list)
            else:
                raise
        else:
            state = SessionResumeHelper(job_list).resume(data, early_cb)
        return cls(state, storage)

    def checkpoint(self):
        """
        Create a checkpoint of the session.

        After calling this method you can later reopen the same session with
        :meth:`SessionManager.open_session()`.
        """
        logger.debug(_("SessionManager.checkpoint()"))
        data = SessionSuspendHelper().suspend(self.state)
        logger.debug(
            _("Saving %d bytes of checkpoint data to %r"),
            len(data), self.storage.location)
        try:
            self.storage.save_checkpoint(data)
        except LockedStorageError:
            self.storage.break_lock()
            self.storage.save_checkpoint(data)

    def destroy(self):
        """
        Destroy all of the filesystem artifacts of the session.

        This basically calls
        :meth:`~plainbox.impl.session.storage.SessionStorage.remove()`
        """
        logger.debug(_("SessionManager.destroy()"))
        self.storage.remove()
