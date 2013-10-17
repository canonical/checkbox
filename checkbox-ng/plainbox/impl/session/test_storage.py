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
:mod:`plainbox.impl.session.test_storage`
=========================================

Test definitions for :mod:`plainbox.impl.session.storage`
"""

from tempfile import TemporaryDirectory
from unittest import TestCase
import os

from plainbox.impl.session.storage import SessionStorage
from plainbox.impl.session.storage import SessionStorageRepository
from plainbox.vendor import mock


class SessionStorageRepositoryTests(TestCase):

    def _populate_dummy_repo(self, repo,
                             session_list=['session1', 'session2'],
                             last_session='session1'):
        # Add session directories
        for session_name in session_list:
            os.mkdir(os.path.join(repo.location, session_name))
        # And a symlink to the last session
        if last_session is not None:
            os.symlink(last_session, os.path.join(
                repo.location, repo._LAST_SESSION_SYMLINK))

    def test_smoke(self):
        # Empty directory looks like an empty repository
        with TemporaryDirectory() as tmp:
            repo = SessionStorageRepository(tmp)
            self.assertEqual(repo.location, tmp)
            self.assertEqual(repo.get_storage_list(), [])
            self.assertEqual(list(iter(repo)), [])
            self.assertEqual(repo.get_last_storage(), None)

    def test_get_storage_list(self):
        # Directory with some sub-directories looks like a repository
        # with a bunch of sessions inside.
        with TemporaryDirectory() as tmp:
            # Create a repository and some dummy data
            repo = SessionStorageRepository(tmp)
            self._populate_dummy_repo(repo)
            # Get a list of storage objects
            storage_list = repo.get_storage_list()
            # Check if we got our data right.
            # The results are not sorted so we sort them for testing
            storage_name_list = [
                os.path.basename(storage.location)
                for storage in storage_list]
            self.assertEqual(
                sorted(storage_name_list), ["session1", "session2"])

    def test_get_last_storage(self):
        # Directory with some sub-directories looks like a repository
        # with a bunch of sessions inside.
        with TemporaryDirectory() as tmp:
            # Create a repository and some dummy data
            repo = SessionStorageRepository(tmp)
            self._populate_dummy_repo(repo)
            # Get the last storage object
            storage = repo.get_last_storage()
            # Check that we got session1
            self.assertEqual(
                os.path.basename(storage.location), 'session1')

    def test_get_last_storage__broken_symlink(self):
        # Directory with some sub-directories looks like a repository
        # with a bunch of sessions inside.
        with TemporaryDirectory() as tmp:
            # Create a repository without any sessions and one broken symlink
            repo = SessionStorageRepository(tmp)
            self._populate_dummy_repo(repo, [], "b0rken")
            # Get the last storage object
            storage = repo.get_last_storage()
            # Make sure it's not valid
            self.assertEqual(storage, None)

    def test_get_default_location_with_XDG_CACHE_HOME(self):
        """
        verify return value of get_default_location() when XDG_CACHE_HOME is
        set and HOME has any value.
        """
        env_patch = {'XDG_CACHE_HOME': 'XDG_CACHE_HOME'}
        with mock.patch.dict('os.environ', values=env_patch):
            measured = SessionStorageRepository.get_default_location()
            expected = "XDG_CACHE_HOME/plainbox/sessions"
            self.assertEqual(measured, expected)

    def test_get_default_location_with_HOME(self):
        """
        verify return value of get_default_location() when XDG_CACHE_HOME is
        not set but HOME is set
        """
        env_patch = {'HOME': 'HOME'}
        with mock.patch.dict('os.environ', values=env_patch, clear=True):
            measured = SessionStorageRepository.get_default_location()
            expected = "HOME/.cache/plainbox/sessions"
            self.assertEqual(measured, expected)


class SessionStorageTests(TestCase):

    def test_smoke(self):
        storage = SessionStorage('foo')
        self.assertEqual(storage.location, 'foo')

    def test_create_remove(self):
        with TemporaryDirectory() as tmp:
            # Create a new storage in the specified directory
            storage = SessionStorage.create(tmp)
            # The location should have been created
            self.assertTrue(os.path.exists(storage.location))
            # And it should be in the directory we indicated
            self.assertEqual(os.path.dirname(storage.location), tmp)
            # There should be a symlink now, pointing to this storage
            self.assertEqual(
                os.readlink(
                    os.path.join(
                        tmp, SessionStorageRepository._LAST_SESSION_SYMLINK)),
                storage.location)
            # Remove the storage now
            storage.remove()
            # And make sure the storage is gone
            self.assertFalse(os.path.exists(storage.location))
            # NOTE: this does not check if the symlink is gone but we don't
            # touch it, it's just left as a dangling link there

    def test_load_save_checkpoint(self):
        with TemporaryDirectory() as tmp:
            # Create a new storage in the specified directory
            storage = SessionStorage.create(tmp)
            # Save some checkpoint data
            data_out = b'some data'
            storage.save_checkpoint(data_out)
            # Load it back
            data_in = storage.load_checkpoint()
            # Check if it's right
            self.assertEqual(data_out, data_in)
