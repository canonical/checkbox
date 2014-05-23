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

from unittest import TestCase

from plainbox.impl.session import SessionManager
from plainbox.impl.session import SessionState
from plainbox.impl.session import SessionStorage
from plainbox.impl.session.suspend import SessionSuspendHelper
from plainbox.vendor import mock


class SessionManagerTests(TestCase):

    def test_state(self):
        """
        verify that accessing SessionManager.state works okay
        """
        storage = mock.Mock(name="storage", spec=SessionStorage)
        state = mock.Mock(name="state", spec=SessionState)
        manager = SessionManager(state, storage)
        self.assertIs(manager.state, state)

    def test_storage(self):
        """
        verify that accessing SessionManager.storage works okay
        """
        storage = mock.Mock(name="storage", spec=SessionStorage)
        state = mock.Mock(name="state", spec=SessionState)
        manager = SessionManager(state, storage)
        self.assertIs(manager.storage, storage)

    def test_checkpoint(self):
        """
        verify that SessionManager.checkpoint() creates an image of the
        suspended session and writes it using the storage system.
        """
        storage = mock.Mock(name="storage", spec=SessionStorage)
        state = mock.Mock(name="state", spec=SessionState)
        manager = SessionManager(state, storage)
        # Mock the suspend helper, we don't want to suspend our mock objects
        helper_name = "plainbox.impl.session.manager.SessionSuspendHelper"
        with mock.patch(helper_name, spec=SessionSuspendHelper) as helper_cls:
            # Call the tested method
            manager.checkpoint()
            # Ensure that a fresh instance of the suspend helper was used to
            # call the suspend() method and that the session state parameter
            # was passed to it.
            helper_cls().suspend.assert_called_with(state)
        # Ensure that save_checkpoint() was called on the storage object with
        # the return value of what the suspend helper produced.
        storage.save_checkpoint.assert_called_with(helper_cls().suspend(state))

    def test_load_session(self):
        """
        verify that SessionManager.load_session() correctly delegates the task
        to various other objects
        """
        # Mock SessionState and job list
        storage = mock.Mock(name="storage", spec=SessionStorage)
        job_list = mock.Mock(name='job_list')
        helper_name = "plainbox.impl.session.manager.SessionResumeHelper"
        with mock.patch(helper_name) as helper_cls:
            helper_cls().resume.return_value = mock.Mock(
                name="state", spec=SessionState)
            manager = SessionManager.load_session(job_list, storage)
        # Ensure that the storage object was used to load the session snapshot
        storage.load_checkpoint.assert_called_with()
        # Ensure that the helper was instantiated with the job list
        helper_cls.assert_called_with(job_list)
        # Ensure that the helper instance was asked to recreate session state
        helper_cls().resume.assert_called_with(storage.load_checkpoint(), None)
        # Ensure that the resulting manager has correct data inside
        self.assertEqual(manager.state, helper_cls().resume())
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
        WellKnownDirsHelper=mock.DEFAULT)
    def test_create_with_state(self, **mocks):
        """
        verify that SessionManager.create_with_state() correctly sets up
        storage repository and creates session directories
        """
        # Mock job list
        state = mock.Mock(name='state', spec=SessionState)
        # Create the new manager
        manager = SessionManager.create_with_state(state)
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
