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
:mod:`plainbox.impl.session.test_storage`
=========================================

Test definitions for :mod:`plainbox.impl.session.storage`
"""

from unittest import TestCase
import os

from plainbox.impl.session.storage import SessionStorage
from plainbox.impl.session.storage import WellKnownDirsHelper


class SessionStorageTests(TestCase):

    def test_smoke(self):
        session_prefix = "test_storage-"
        storage = SessionStorage(session_prefix)
        session_id = storage.id
        self.assertEqual(storage.location,
                         WellKnownDirsHelper.session_dir(session_id))

    def test_create_remove(self):
        session_prefix = "test_storage-"
        # Create a new storage in the specified directory
        storage = SessionStorage.create(session_prefix)
        session_id = storage.id
        # The location should have been created
        self.assertTrue(os.path.exists(storage.location))
        # And it should be in the directory we indicated
        self.assertEqual(os.path.dirname(storage.location),
                         os.path.dirname(WellKnownDirsHelper.session_dir(
                             session_id)))
        # Remove the storage now
        storage.remove()
        # And make sure the storage is gone
        self.assertFalse(os.path.exists(storage.location))

    def test_load_save_checkpoint(self):
        session_prefix = "test_storage-"
        # Create a new storage in the specified directory
        storage = SessionStorage.create(session_prefix)
        # Save some checkpoint data
        data_out = b'some data'
        storage.save_checkpoint(data_out)
        # Load it back
        data_in = storage.load_checkpoint()
        # Check if it's right
        self.assertEqual(data_out, data_in)
        # Remove the storage now
        storage.remove()
