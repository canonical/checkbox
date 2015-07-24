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

from collections import OrderedDict
import contextlib
import errno
import logging
import os

from plainbox.i18n import gettext as _, ngettext
from plainbox.impl import pod
from plainbox.impl.session.resume import SessionResumeHelper
from plainbox.impl.session.state import SessionDeviceContext
from plainbox.impl.session.state import SessionState
from plainbox.impl.session.storage import LockedStorageError
from plainbox.impl.session.storage import SessionStorage
from plainbox.impl.session.storage import SessionStorageRepository
from plainbox.impl.session.suspend import SessionSuspendHelper
from plainbox.impl.unit.testplan import TestPlanUnit
from plainbox.public import get_providers
from plainbox.vendor import morris

logger = logging.getLogger("plainbox.session.manager")


class WellKnownDirsHelper(pod.POD):
    """
    Helper class that knows about well known directories for SessionStorage.

    This class simply gets rid of various magic directory names that we
    associate with session storage. It also provides a convenience utility
    method :meth:`populate()` to create all of those directories, if needed.
    """

    storage = pod.Field(
        doc="SessionStorage associated with this helper",
        type=SessionStorage,
        initial=pod.MANDATORY,
        assign_filter_list=[pod.const, pod.typed])

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


def at_most_one_context_filter(
    instance: pod.POD, field: pod.Field, old: "Any", new: "Any"
):
    if len(new) > 1:
        raise ValueError(_(
            "session manager currently doesn't support sessions"
            " involving multiple devices (a.k.a multi-node testing)"
        ))
    return new


class SessionManager(pod.POD):
    """
    Manager class for coupling SessionStorage with SessionState.

    This class allows application code to manage disk state of sessions. Using
    the :meth:`checkpoint()` method applications can create persistent
    snapshots of the :class:`~plainbox.impl.session.state.SessionState`
    associated with each :class:`SessionManager`.
    """

    device_context_list = pod.Field(
        doc="""
        A list of session device context objects

        .. note::
            You must not modify this field directly.

            This is not enforced but please use the
            :meth:`add_device_context()` or :meth:`remove_device_context()` if
            you want to manipulate the list.  Currently you cannot reorder the
            list of context objects.
        """,
        type=list,
        initial=pod.MANDATORY,
        assign_filter_list=[
            pod.typed, pod.typed.sequence(SessionDeviceContext),
            pod.const, at_most_one_context_filter])

    storage = pod.Field(
        doc="A SesssionStorage instance",
        type=SessionStorage,
        initial=pod.MANDATORY,
        assign_filter_list=[pod.typed, pod.const])

    def _on_test_plans_changed(self, old: "Any", new: "Any") -> None:
        self._propagate_test_plans()

    test_plans = pod.Field(
        doc="""
        Test plans that this session is processing.

        This field contains a tuple of test plans that are active in the
        session. Any changes here are propagated to each device context
        participating in the session. This in turn makes all of the overrides
        defined by those test plans effective.

        .. note::
            Currently there is no facitly that would allow to use this field to
            drive test execution. Such facility is likely to be added later.
        """,
        type=tuple,
        initial=(),
        notify=True,
        notify_fn=_on_test_plans_changed,
        assign_filter_list=[
            pod.typed, pod.typed.sequence(TestPlanUnit), pod.unique])

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
        data = SessionSuspendHelper().suspend(
            self.state, self.storage.location)
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
        return context

    def add_local_device_context(self):
        """
        Create and add a SessionDeviceContext that describes the local device.

        The local device is always the device executing plainbox. Other devices
        may execute jobs or parts of plainbox but they don't need to store or
        run the full plainbox code.
        """
        return self.add_device_context(SessionDeviceContext())

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

    @morris.signal
    def on_device_context_added(self, context):
        """
        Signal fired when a session device context object is added
        """
        logger.debug(
            _("Device context %s added to session manager %s"),
            context, self)
        self._propagate_test_plans()

    @morris.signal
    def on_device_context_removed(self, context):
        """
        Signal fired when a session device context object is removed
        """
        logger.debug(
            _("Device context %s removed from session manager %s"),
            context, self)
        self._propagate_test_plans()

    def _too_many_device_context_objects(self):
        raise ValueError(_(
            "session manager currently doesn't support sessions"
            " involving multiple devices (a.k.a multi-node testing)"
        ))

    def _propagate_test_plans(self):
        logger.debug(_("Propagating test plans to all devices"))
        test_plans = self.test_plans
        for context in self.device_context_list:
            context.set_test_plan_list(test_plans)

    @property
    def exporter_map(self):
        """ Map from exporter id to the corresponding exporter unit. """
        exporter_map = OrderedDict()
        for unit in self.state.unit_list:
            if unit.Meta.name == 'exporter':
                support = unit.support
                if support:
                    exporter_map[unit.id] = support
        # Patch exporter map to expose short names
        legacy_mapping = {
            '2013.com.canonical.plainbox::hexr': 'xml',
            '2013.com.canonical.plainbox::html': 'html',
            '2013.com.canonical.plainbox::json': 'json',
            '2013.com.canonical.plainbox::rfc822': 'rfc822',
            '2013.com.canonical.plainbox::text': 'text',
            '2013.com.canonical.plainbox::xlsx': 'xlsx'
        }
        for new_id, legacy_id in legacy_mapping.items():
            if new_id in exporter_map:
                exporter_map[legacy_id] = exporter_map[new_id]
        return exporter_map

    def create_exporter(self, exporter_id, option_list=(), strict=True):
        """
        Create an exporter object with the specified name and options.

        :param exporter_id:
            Identifier of the exporter unit (which must have been loaded
            into the session device context of the first device). For
            backwards compatibility this can also be any of the legacy
            identifiers ``xml``, ``html``, ``json``, ``rfc822``, ``text`` or
            ``xlsx``.
        :param option_list:
            (optional) A list of options to pass to the exporter. Each option
            is a string. Some strings may be of form 'key=value' but those are
            handled by each exporter separately. By default an empty tuple is
            used so no special options are enabled.
        :param strict:
            (optional) Strict mode, in this mode ``option_list`` must not
            contain any options that are unrecognized by the exporter. Since
            many options (but not all) are shared among various exporters,
            using non-strict mode might make it easier to use a single superset
            of options to all exporters and let them silently ignore those that
            they don't understand.
        :raises LookupError:
            If the exporter identifier cannot be found. Note that this might
            indicate that appropriate provider has not been loaded yet.
        :returns:
            A ISessionStateExporter instance with appropriate configuration.
        """
        exporter_support = self.exporter_map[exporter_id]
        if not strict:
            # In non-strict mode silently discard unsupported options.
            supported_options = frozenset(
                exporter_support.exporter_cls.supported_option_list)
            option_list = [
                item for item in option_list if item in supported_options
            ]
        return exporter_support.exporter_cls(
            option_list, exporter_unit=exporter_support)

    @classmethod
    @contextlib.contextmanager
    def get_throwaway_manager(cls, provider_list=None):
        """
        Create a temporary session manager.

        :param provider_list:
            (optional) A list of providers to put into the session manager. By
            default all known providers are added. You can use this argument to
            customize the behaviour beyond defaults.
        :returns:
            A new SessionManager object that will be destroyed when the context
            manager is left.

        This method can be used to create a throw-away session manager which is
        not really meant for running jobs but can be useful to access exporters
        and other objects stored in providers.
        """
        if provider_list is None:
            provider_list = get_providers()
            manager = cls.create()
        try:
            manager.add_local_device_context()
            device_context = manager.default_device_context
            for provider in provider_list:
                device_context.add_provider(provider)
            yield manager
        finally:
            manager.destroy()
