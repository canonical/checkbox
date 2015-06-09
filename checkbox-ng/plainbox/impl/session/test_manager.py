# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
plainbox.impl.test_manager
==========================

Test definitions for plainbox.impl.session.manager module
"""

from unittest import expectedFailure

from plainbox.abc import IJobDefinition
from plainbox.impl.session import SessionManager
from plainbox.impl.session import SessionState
from plainbox.impl.session import SessionStorage
from plainbox.impl.session.state import SessionDeviceContext
from plainbox.impl.session.suspend import SessionSuspendHelper
from plainbox.vendor import mock
from plainbox.vendor.morris import SignalTestCase


class SessionManagerTests(SignalTestCase):

    def setUp(self):
        self.storage = mock.Mock(name="storage", spec=SessionStorage)
        self.state = mock.Mock(name="state", spec=SessionState)
        self.context = mock.Mock(name="context", spec=SessionDeviceContext)
        self.context2 = mock.Mock(
            name='context2', spec_set=SessionDeviceContext)
        self.context_list = [self.context]  # NOTE: just the first context
        self.manager = SessionManager(self.context_list, self.storage)

    def test_device_context_list(self):
        """
        Verify that accessing SessionManager.device_context_list works okay
        """
        self.assertEqual(self.manager.device_context_list, self.context_list)

    def test_default_device_context__typical(self):
        """
        Verify that accessing SessionManager.default_device_context returns
        the first context from the context list
        """
        self.assertEqual(self.manager.default_device_context, self.context)

    def test_default_device_context__no_contexts(self):
        """
        Verify that accessing SessionManager.default_device_context returns
        None when the manager doesn't have any device context objects yet
        """
        manager = SessionManager([], self.storage)
        self.assertIsNone(manager.default_device_context, None)

    def test_state(self):
        """
        verify that accessing SessionManager.state works okay
        """
        self.assertIs(self.manager.state, self.context.state)

    def test_storage(self):
        """
        verify that accessing SessionManager.storage works okay
        """
        self.assertIs(self.manager.storage, self.storage)

    def test_checkpoint(self):
        """
        verify that SessionManager.checkpoint() creates an image of the
        suspended session and writes it using the storage system.
        """
        # Mock the suspend helper, we don't want to suspend our mock objects
        helper_name = "plainbox.impl.session.manager.SessionSuspendHelper"
        with mock.patch(helper_name, spec=SessionSuspendHelper) as helper_cls:
            # Call the tested method
            self.manager.checkpoint()
            # Ensure that a fresh instance of the suspend helper was used to
            # call the suspend() method and that the session state parameter
            # was passed to it.
            helper_cls().suspend.assert_called_with(
                self.context.state, self.storage.location)
        # Ensure that save_checkpoint() was called on the storage object with
        # the return value of what the suspend helper produced.
        self.storage.save_checkpoint.assert_called_with(
            helper_cls().suspend(self.context.state))

    def test_load_session(self):
        """
        verify that SessionManager.load_session() correctly delegates the task
        to various other objects
        """
        job = mock.Mock(name='job', spec_set=IJobDefinition)
        unit_list = [job]
        flags = None
        helper_name = "plainbox.impl.session.manager.SessionResumeHelper"
        with mock.patch(helper_name) as helper_cls:
            resumed_state = mock.Mock(spec_set=SessionState)
            resumed_state.unit_list = unit_list
            helper_cls().resume.return_value = resumed_state
            # NOTE: mock away _propagate_test_plans() so that we don't get
            # unwanted side effects we're not testing here.
            with mock.patch.object(SessionManager, '_propagate_test_plans'):
                manager = SessionManager.load_session(unit_list, self.storage)
        # Ensure that the storage object was used to load the session snapshot
        self.storage.load_checkpoint.assert_called_with()
        # Ensure that the helper was instantiated with the unit list, flags and
        # location
        helper_cls.assert_called_with(unit_list, flags, self.storage.location)
        # Ensure that the helper instance was asked to recreate session state
        helper_cls().resume.assert_called_with(
            self.storage.load_checkpoint(), None)
        # Ensure that the resulting manager has correct data inside
        self.assertEqual(manager.state, helper_cls().resume())
        self.assertEqual(manager.storage, self.storage)

    @mock.patch.multiple(
        "plainbox.impl.session.manager", spec_set=True,
        SessionStorageRepository=mock.DEFAULT,
        SessionStorage=mock.DEFAULT,
        WellKnownDirsHelper=mock.DEFAULT)
    def test_create(self, **mocks):
        """
        verify that SessionManager.create() correctly sets up
        storage repository and creates session directories
        """
        mocks['SessionStorage'].create.return_value = mock.MagicMock(
            spec_set=SessionStorage)
        # Create the new manager
        manager = SessionManager.create()
        # Ensure that a default repository was created
        mocks['SessionStorageRepository'].assert_called_with()
        repo = mocks['SessionStorageRepository']()
        # Ensure that a storage was created, with repository location and
        # without legacy mode turned on
        mocks['SessionStorage'].create.assert_called_with(repo.location, False)
        storage = mocks['SessionStorage'].create()
        # Ensure that a default directories were created
        mocks['WellKnownDirsHelper'].assert_called_with(storage)
        helper = mocks['WellKnownDirsHelper']()
        helper.populate.assert_called_with()
        # Ensure that the resulting manager has correct data inside
        self.assertEqual(manager.device_context_list, [])
        self.assertEqual(manager.storage, storage)

    @mock.patch.multiple(
        "plainbox.impl.session.manager", spec_set=True,
        SessionStorageRepository=mock.DEFAULT,
        SessionState=mock.DEFAULT,
        SessionStorage=mock.DEFAULT,
        WellKnownDirsHelper=mock.DEFAULT)
    def test_create_with_unit_list(self, **mocks):
        """
        verify that SessionManager.create_with_unit_list() correctly sets up
        storage repository and creates session directories
        """
        mocks['SessionStorage'].create.return_value = mock.MagicMock(
            spec_set=SessionStorage)
        # Mock unit list
        unit_list = mock.Mock(name='unit_list')
        # Create the new manager
        manager = SessionManager.create_with_unit_list(unit_list)
        # Ensure that a state object was created
        mocks['SessionState'].assert_called_with(unit_list)
        state = mocks['SessionState']()
        # Ensure that a default repository was created
        mocks['SessionStorageRepository'].assert_called_with()
        repo = mocks['SessionStorageRepository']()
        # Ensure that a storage was created, with repository location and
        # without legacy mode turned on
        mocks['SessionStorage'].create.assert_called_with(repo.location, False)
        storage = mocks['SessionStorage'].create()
        # Ensure that a default directories were created
        mocks['WellKnownDirsHelper'].assert_called_with(storage)
        helper = mocks['WellKnownDirsHelper']()
        helper.populate.assert_called_with()
        # Ensure that the resulting manager has correct data inside
        self.assertEqual(manager.state, state)
        self.assertEqual(manager.storage, storage)

    @mock.patch.multiple(
        "plainbox.impl.session.manager", spec_set=True,
        SessionStorageRepository=mock.DEFAULT,
        SessionState=mock.DEFAULT,
        SessionStorage=mock.DEFAULT,
        SessionDeviceContext=mock.DEFAULT,
        WellKnownDirsHelper=mock.DEFAULT)
    def test_create_with_state(self, **mocks):
        """
        verify that SessionManager.create_with_state() correctly sets up
        storage repository and creates session directories
        """
        mocks['SessionStorage'].create.return_value = mock.MagicMock(
            spec_set=SessionStorage)
        # Mock an empty list of units in teh session state object
        self.state.unit_list = []
        # Create the new manager
        manager = SessionManager.create_with_state(self.state)
        # Ensure that a default repository was created
        mocks['SessionStorageRepository'].assert_called_with()
        repo = mocks['SessionStorageRepository']()
        # Ensure that a storage was created, with repository location and
        # without legacy mode turned on
        mocks['SessionStorage'].create.assert_called_with(repo.location, False)
        storage = mocks['SessionStorage'].create()
        # Ensure that a default directories were created
        mocks['WellKnownDirsHelper'].assert_called_with(storage)
        helper = mocks['WellKnownDirsHelper']()
        helper.populate.assert_called_with()
        # Ensure that the device context was created with the right state
        # object
        mocks['SessionDeviceContext'].assert_called_with(self.state)
        # Ensure that the resulting manager has correct data inside
        self.assertEqual(
            manager.device_context_list, [mocks['SessionDeviceContext']()])
        # self.assertEqual(manager.state, self.state)
        self.assertEqual(manager.storage, storage)

    def test_add_device_context(self):
        """
        Ensure that adding a device context works
        """
        manager = SessionManager([], self.storage)
        manager.add_device_context(self.context)
        self.assertIn(self.context, manager.device_context_list)

    @expectedFailure
    def test_add_device_context__add_another(self):
        """
        Ensure that adding a second context also works
        """
        manager = SessionManager([], self.storage)
        manager.add_device_context(self.context)
        manager.add_device_context(self.context2)
        self.assertIn(self.context, manager.device_context_list)
        self.assertIn(self.context2, manager.device_context_list)

    def test_add_device_context__twice(self):
        """
        Ensure that you cannot add the same device context twice
        """
        manager = SessionManager([], self.storage)
        manager.add_device_context(self.context)
        with self.assertRaises(ValueError):
            manager.add_device_context(self.context)

    def test_remove_context(self):
        """
        Ensure that removing a device context works
        """
        manager = SessionManager([], self.storage)
        manager.add_device_context(self.context)
        manager.remove_device_context(self.context)
        self.assertNotIn(self.context, manager.device_context_list)

    def test_remove_context__missing(self):
        """
        Ensure that you cannot remove a device context that is not added first
        """
        with self.assertRaises(ValueError):
            self.manager.remove_device_context(self.context2)

    def test_on_device_context_added(self):
        """
        Ensure that adding a device context sends the appropriate signal
        """
        manager = SessionManager([], self.storage)
        self.watchSignal(manager.on_device_context_added)
        manager.add_device_context(self.context)
        self.assertSignalFired(manager.on_device_context_added, self.context)

    def test_on_device_context_removed(self):
        """
        Ensure that removing a device context sends the appropriate signal
        """
        manager = SessionManager([self.context], self.storage)
        self.watchSignal(manager.on_device_context_removed)
        manager.remove_device_context(self.context)
        self.assertSignalFired(manager.on_device_context_removed, self.context)

    def test_add_local_device_context(self):
        """
        Ensure that using add_local_device_context() adds a context with
        a special 'local' device and fires the appropriate signal
        """
        manager = SessionManager([], self.storage)
        self.watchSignal(manager.on_device_context_added)
        cls_name = "plainbox.impl.session.manager.SessionDeviceContext"
        with mock.patch(cls_name) as sdc:
            manager.add_local_device_context()
            self.assertSignalFired(manager.on_device_context_added, sdc())
            self.assertIn(sdc(), manager.device_context_list)
