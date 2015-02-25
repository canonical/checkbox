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

from plainbox.i18n import gettext as _, ngettext
from plainbox.impl.session.resume import SessionResumeHelper
from plainbox.impl.session.state import SessionDeviceContext
from plainbox.impl.session.state import SessionState
from plainbox.impl.session.storage import LockedStorageError
from plainbox.impl.session.storage import SessionStorage
from plainbox.impl.session.storage import SessionStorageRepository
from plainbox.impl.session.suspend import SessionSuspendHelper
from plainbox.vendor.morris import signal

logger = logging.getLogger("plainbox.session.manager")


class WellKnownDirsHelper:
    """
    Helper class that knows about well known directories for SessionStorage.

    This class simply gets rid of various magic directory names that we
    associate with session storage. It also provides a convenience utility
    method :meth:`populate()` to create all of those directories, if needed.
    """

    def __init__(self, storage):
        # assert isinstance(storage, SessionStorage)
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

    def __init__(self, device_context_list, storage):
        """
        Initialize a manager with a list of session device context objects and
        a storage object that will be used for managing storage for all testing
        related to those objects.

        :param device_context_list:
            A list of SessionDeviceContext instances. Currently at most one
            object may exist in that list but this restriction will be lifted
            later on without changing the interface.
        :param storage:
            A SessionStorage instance.
        """
        if len(device_context_list) > 1:
            self._too_many_device_context_objects()
        self._device_context_list = device_context_list
        self._storage = storage
        logger.debug(
            # TRANSLATORS: please don't translate 'SessionManager'
            # and 'device_context_list'
            _("Created SessionManager with device_context_list:%r"
              " and storage:%r"), device_context_list, storage)

    @property
    def device_context_list(self):
        """
        A list of session device context objects

        .. note::
            You must not modify the return value.

            This is not enforced but please use the
            :meth:`add_device_context()` or :meth:`remove_device_context()` if
            you want to manipulate the list.  Currently you cannot reorder the
            list of context objects.
        """
        return self._device_context_list

    @property
    def default_device_context(self):
        """
        The default (first) session device context if available

        In single-device sessions this is the context that is used to execute
        every single job definition. Applications that use multiple devices
        must access and use the context list directly.

        .. note:
            The default context may be none if there are no context objects
            present in the session. This is never the case for applications
            using the single-device APIs.
        """
        return (self.device_context_list[0]
                if len(self.device_context_list) > 0 else None)

    @property
    def state(self):
        """
        :class:`~plainbox.impl.session.state.SessionState` associated with this
        manager
        """
        if self.default_device_context is not None:
            return self.default_device_context.state

    @property
    def storage(self):
        """
        :class:`~plainbox.impl.session.storage.SessionStorage` associated with
        this manager
        """
        return self._storage

    @classmethod
    def create(cls, repo=None, legacy_mode=False):
        """
        Create an empty session manager.

        This method creates an empty session manager. This is the most generic
        API that allows applications to freely work with any set of devices.

        Typically applications will use the :meth:`add_device_context()` method
        to add additional context objects at a later time. This method creates
        and populates the session storage with all of the well known
        directories (using :meth:`WellKnownDirsHelper.populate()`).

        :param repo:
            If specified then this particular repository will be used to create
            the storage for this session. If left out, a new repository is
            constructed with the default location.
        :ptype repo:
            :class:`~plainbox.impl.session.storage.SessionStorageRepository`.
        :param legacy_mode:
            Propagated to
            :meth:`~plainbox.impl.session.storage.SessionStorage.create()` to
            ensure that legacy (single session) mode is used.
        :ptype legacy_mode:
            bool
        :return:
            fresh :class:`SessionManager` instance
        """
        logger.debug("SessionManager.create()")
        if repo is None:
            repo = SessionStorageRepository()
        storage = SessionStorage.create(repo.location, legacy_mode)
        WellKnownDirsHelper(storage).populate()
        return cls([], storage)

    @classmethod
    def create_with_state(cls, state, repo=None, legacy_mode=False):
        """
        Create a session manager by wrapping existing session state.

        This method populates the session storage with all of the well known
        directories (using :meth:`WellKnownDirsHelper.populate()`)

        :param stage:
            A pre-existing SessionState object.
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
        logger.debug("SessionManager.create_with_state()")
        if repo is None:
            repo = SessionStorageRepository()
        storage = SessionStorage.create(repo.location, legacy_mode)
        WellKnownDirsHelper(storage).populate()
        context = SessionDeviceContext(state)
        return cls([context], storage)

    @classmethod
    def create_with_unit_list(cls, unit_list=None, repo=None,
                              legacy_mode=False):
        """
        Create a session manager with a fresh session.

        This method populates the session storage with all of the well known
        directories (using :meth:`WellKnownDirsHelper.populate()`)

        :param unit_list:
            If specified then this will be the initial list of units known by
            the session state object.
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
        logger.debug("SessionManager.create_with_unit_list()")
        if unit_list is None:
            unit_list = []
        state = SessionState(unit_list)
        if repo is None:
            repo = SessionStorageRepository()
        storage = SessionStorage.create(repo.location, legacy_mode)
        context = SessionDeviceContext(state)
        WellKnownDirsHelper(storage).populate()
        return cls([context], storage)

    @classmethod
    def load_session(cls, unit_list, storage, early_cb=None, flags=None):
        """
        Load a previously checkpointed session.

        This method allows one to re-open a session that was previously
        created by :meth:`SessionManager.checkpoint()`

        :param unit_list:
            List of all known units. This argument is used to reconstruct the
            session from a dormant state. Since the suspended data cannot
            capture implementation details of each unit reliably, actual units
            need to be provided externally. Unlike in :meth:`create_session()`
            this list really needs to be complete, it must also include any
            generated units.
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
        :param flags:
            An optional set of flags that may influence the resume process.
            Currently this is an internal implementation detail and no "public"
            flags are provided. Passing None here is a safe equvalent of using
            this API before it was introduced.
        :raises:
            Anything that can be raised by
            :meth:`~plainbox.impl.session.storage.SessionStorage.
            load_checkpoint()` and :meth:`~plainbox.impl.session.suspend.
            SessionResumeHelper.resume()`
        :returns:
            Fresh instance of :class:`SessionManager`
        """
        logger.debug("SessionManager.load_session()")
        try:
            data = storage.load_checkpoint()
        except IOError as exc:
            if exc.errno == errno.ENOENT:
                state = SessionState(unit_list)
            else:
                raise
        else:
            state = SessionResumeHelper(
                unit_list, flags, storage.location
            ).resume(data, early_cb)
        context = SessionDeviceContext(state)
        return cls([context], storage)

    def checkpoint(self):
        """
        Create a checkpoint of the session.

        After calling this method you can later reopen the same session with
        :meth:`SessionManager.load_session()`.
        """
        logger.debug("SessionManager.checkpoint()")
        data = SessionSuspendHelper().suspend(self.state)
        logger.debug(
            ngettext(
                "Saving %d byte of checkpoint data to %r",
                "Saving %d bytes of checkpoint data to %r", len(data)
            ), len(data), self.storage.location)
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
        logger.debug("SessionManager.destroy()")
        self.storage.remove()

    def add_device_context(self, context):
        """
        Add a device context to the session manager

        :param context:
            The :class:`SessionDeviceContext` to add.
        :raises ValueError:
            If the context is already in the session manager or the device
            represented by that context is already present in the session
            manager.

        This method fires the :meth:`on_device_context_added()` signal
        """
        if any(other_context.device == context.device
               for other_context in self.device_context_list):
            raise ValueError(
                _("attmpting to add a context for device {} which is"
                  " already represented in this session"
                  " manager").format(context.device))
        if len(self.device_context_list) > 0:
            self._too_many_device_context_objects()
        self.device_context_list.append(context)
        self.on_device_context_added(context)

    def add_local_device_context(self):
        """
        Create and add a SessionDeviceContext that describes the local device.

        The local device is always the device executing plainbox. Other devices
        may execute jobs or parts of plainbox but they don't need to store or
        run the full plainbox code.
        """
        self.add_device_context(SessionDeviceContext())

    def remove_device_context(self, context):
        """
        Remove an device context from the session manager

        :param unit:
            The :class:`SessionDeviceContext` to remove.

        This method fires the :meth:`on_device_context_removed()` signal
        """
        if context not in self.device_context_list:
            raise ValueError(_(
                "attempting to remove a device context not present in this"
                " session manager"))
        self.device_context_list.remove(context)
        self.on_device_context_removed(context)

    @signal
    def on_device_context_added(self, context):
        """
        Signal fired when a session device context object is added
        """
        logger.debug(
            _("Device context %s added to session manager %s"),
            context, self)

    @signal
    def on_device_context_removed(self, context):
        """
        Signal fired when a session device context object is removed
        """
        logger.debug(
            _("Device context %s removed from session manager %s"),
            context, self)

    def _too_many_device_context_objects(self):
        raise ValueError(_(
            "session manager currently doesn't support sessions"
            " involving multiple devices (a.k.a multi-node testing)"
        ))
