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
:mod:`plainbox.impl.session.storage` -- storage for sessions
============================================================

This module contains storage support code for handling sessions. Each location
is wrapped by a :class:`SessionStorage` instance. That latter class be used to
create (allocate) and remove all of the files associated with a particular
session.
"""

import datetime
import errno
import logging
import os
import shutil
import stat

from plainbox.i18n import gettext as _, ngettext
from plainbox.impl.runner import slugify

logger = logging.getLogger("plainbox.session.storage")


class WellKnownDirsHelper():
    """
    Helper class that knows about well known directories and paths.

    This class simply gets rid of various magic path names that are used during
    an checkbox invocation. The methods :meth:`populate_base()` and
    :meth:`populate_session()` are convenience utilities to create the
    directory structure and ensure permissions are correct.
    """

    base_of_everything = '/var/tmp/checkbox-ng'

    @classmethod
    def populate_base(cls):
        """
        Create all of the well known static directories that are not session
        specific
        """
        oldmask = os.umask(000)
        for dirname in cls._base_directories():
            if not os.path.exists(dirname):
                os.makedirs(dirname)
                # TODO: test that is 0o777 and if not attempt to fix?
        os.umask(oldmask)

    @classmethod
    def populate_session(cls, session_id):
        """
        Create the session specific directories
        """
        oldmask = os.umask(000)
        for dirname in cls._session_directories(session_id):
            if not os.path.exists(dirname):
                os.makedirs(dirname)
        os.umask(oldmask)
        return cls.session_dir(session_id)

    @classmethod
    def _base_directories(cls):
        return [cls.base_of_everything, cls.session_repository()]

    @classmethod
    def _session_directories(cls, session_id):
        return [cls.session_dir(session_id),
                cls.session_share(session_id),
                cls.io_logs(session_id)]

    @classmethod
    def session_repository(cls):
        return os.path.join(cls.base_of_everything, "sessions")

    @classmethod
    def session_dir(cls, session_id):
        return os.path.join(cls.session_repository(),
                            "{}.{}".format(session_id, "session"))

    @classmethod
    def io_logs(cls, session_id):
        return os.path.join(cls.session_dir(session_id), "io-logs")

    @classmethod
    def session_share(cls, session_id):
        return os.path.join(cls.session_dir(session_id), "session-share")

    @classmethod
    def manifest_file(cls):
        return os.path.join(cls.base_of_everything, "machine-manifest.json")

    @classmethod
    def get_storage_list(self):
        """
        Enumerate stored sessions in the repository.

        If the repository directory is not present then an empty list is
        returned.

        :returns:
            list of :class:`SessionStorage` representing discovered sessions
            sorted by their age (youngest first)
        """
        repo = WellKnownDirsHelper().session_repository()
        logger.debug(_("Enumerating sessions in %s"), repo)
        try:
            # Try to enumerate the directory
            item_list = sorted(os.listdir(repo),
                               key=lambda x: os.stat(os.path.join(
                                   repo, x)).st_mtime, reverse=True)
        except OSError as exc:
            # If the directory does not exist,
            # silently return empty collection
            if exc.errno == errno.ENOENT:
                return []
            # Don't silence any other errors
            raise
        session_list = []
        # Check each item by looking for directories
        for item in item_list:
            pathname = os.path.join(repo, item)
            # Make sure not to follow any symlinks here
            stat_result = os.lstat(pathname)
            # Consider non-hidden directories that end with the word .session
            if (not item.startswith(".") and item.endswith(".session")
                    and stat.S_ISDIR(stat_result.st_mode)):
                logger.debug(_("Found possible session in %r"), pathname)
                session = SessionStorage(os.path.splitext(item)[0])
                session_list.append(session)
        # Return the full list
        return session_list


class LockedStorageError(IOError):
    """
    Exception raised when SessionStorage.save_checkpoint() finds an existing
    'next' file from a (presumably) previous call to save_checkpoint() that
    got interrupted
    """


class SessionStorage:
    """
    Abstraction for storage area that is used by :class:`SessionState` to
    keep some persistent and volatile data.

    This class implements functions performing input/output operations
    on session checkpoint data. The location property can be used for keeping
    any additional files or directories but keep in mind that they will
    be removed by :meth:`SessionStorage.remove()`

    This class indirectly collaborates with :class:`SessionSuspendHelper` and
    :class:`SessionResumeHelper`.
    """

    _SESSION_FILE = 'session'

    _SESSION_FILE_NEXT = 'session.next'

    def __init__(self, id):
        """
        Initialize a :class:`SessionStorage` with the given location.

        The location is not created. If you want to ensure that it exists
        call :meth:`create()` instead.
        """
        self._id = id

    def __repr__(self):
        return "<{} location:{!r}>".format(
            self.__class__.__name__, self.location)

    @property
    def location(self):
        """
        location of the session storage
        """
        return WellKnownDirsHelper.session_dir(self.id)

    @property
    def id(self):
        """
        identifier of the session storage (name of the random directory)
        """
        return self._id

    @property
    def session_file(self):
        """
        pathname of the session state file
        """
        return os.path.join(self.location, self._SESSION_FILE)

    @classmethod
    def create(cls, prefix='pbox-'):
        """
        Create a new :class:`SessionStorage` in a subdirectory of the base
        directory. The directory structure will be created if it does not exist
        and will writable by any user.

        :param prefix:
            String which should prefix all session filenames. The prefix is
            sluggified before use.
        """
        WellKnownDirsHelper.populate_base()

        isoformat = "%Y-%m-%dT%H.%M.%S"
        timestamp = datetime.datetime.utcnow().strftime(isoformat)
        session_id = "{prefix}{timestamp}".format(prefix=slugify(prefix),
                                                  timestamp=timestamp)
        uniq = 1
        while os.path.exists(WellKnownDirsHelper.session_dir(session_id)):
            session_id = "{prefix}{timestamp}_({uniq})".format(
                prefix=slugify(prefix), timestamp=timestamp, uniq=uniq)
            uniq += 1
        session_dir = WellKnownDirsHelper.populate_session(session_id)

        logger.debug(_("Created new storage in %r"), session_dir)
        self = cls(session_id)
        return self

    def remove(self):
        """
        Remove all filesystem entries associated with this instance.
        """
        logger.debug(_("Removing session storage from %r"), self.location)

        def error_handler(function, path, excinfo):
            logger.warning(_("Cannot remove %s"), path)
        shutil.rmtree(self.location, onerror=error_handler)

    def load_checkpoint(self):
        """
        Load checkpoint data from the filesystem

        :returns: data from the most recent checkpoint
        :rtype: bytes

        :raises IOError, OSError:
            on various problems related to accessing the filesystem
        """
        # Open the location directory
        location_fd = os.open(self.location, os.O_DIRECTORY)
        try:
            # Open the current session file in the location directory
            session_fd = os.open(
                self._SESSION_FILE, os.O_RDONLY, dir_fd=location_fd)
            # Stat the file to know how much to read
            session_stat = os.fstat(session_fd)
            try:
                # Read session data
                data = os.read(session_fd, session_stat.st_size)
                if len(data) != session_stat.st_size:
                    raise IOError(_("partial read?"))
            finally:
                # Close the session file
                os.close(session_fd)
        except IOError as exc:
            if exc.errno == errno.ENOENT:
                # Treat lack of 'session' file as an empty file
                return b''
            raise
        else:
            return data
        finally:
            # Close the location directory
            os.close(location_fd)

    def save_checkpoint(self, data):
        """
        Save checkpoint data to the filesystem.

        The directory associated with this :class:`SessionStorage` must already
        exist. Typically the instance should be obtained by calling
        :meth:`SessionStorage.create()` which will ensure that this is already
        the case.

        :raises TypeError:
            if data is not a bytes object.

        :raises LockedStorageError:
            if leftovers from previous save_checkpoint() have been detected.
            Normally those should never be here but in certain cases that is
            possible. Callers might want to call :meth:`break_lock()`
            to resolve the problem and try again.

        :raises IOError, OSError:
            on various problems related to accessing the filesystem.
            Typically permission errors may be reported here.
        """
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        logger.debug(ngettext(
            "Saving %d byte of data (%s)",
            "Saving %d bytes of data (%s)",
            len(data)), len(data), "UNIX, python 3.3 or newer")
        # Open the location directory, we need to fsync that later
        # XXX: this may fail, maybe we should keep the fd open all the time?
        location_fd = os.open(self.location, os.O_DIRECTORY)
        logger.debug(
            _("Opened %r as descriptor %d"), self.location, location_fd)
        try:
            # Open the "next" file in the location_directory
            #
            # Use openat(2) to ensure we always open a file relative to the
            # directory we already opened above. This is essential for fsync(2)
            # calls made below.
            #
            # Use "write" + "create" + "exclusive" flags so that no race
            # condition is possible.
            #
            # This will never return -1, it throws IOError when anything is
            # wrong. The caller has to catch this.
            #
            # As a special exception, this code handles EEXISTS
            # (FIleExistsError) and converts that to LockedStorageError
            # that can be especially handled by some layer above.
            try:
                next_session_fd = os.open(
                    self._SESSION_FILE_NEXT,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644,
                    dir_fd=location_fd)
            except FileExistsError:
                raise LockedStorageError()
            logger.debug(
                _("Opened next session file %s as descriptor %d"),
                self._SESSION_FILE_NEXT, next_session_fd)
            try:
                # Write session data to disk
                #
                # I cannot find conclusive evidence but it seems that
                # os.write() handles partial writes internally. In case we do
                # get a partial write _or_ we run out of disk space, raise an
                # explicit IOError.
                num_written = os.write(next_session_fd, data)
                logger.debug(ngettext(
                    "Wrote %d byte of data to descriptor %d",
                    "Wrote %d bytes of data to descriptor %d", num_written),
                    num_written, next_session_fd)
                if num_written != len(data):
                    raise IOError(_("partial write?"))
            except Exception as exc:
                logger.warning(_("Unable to complete write: %r"), exc)
                # If anything goes wrong we should unlink the next file. As
                # with the open() call above we use unlinkat to prevent race
                # conditions.
                # TRANSLATORS: unlinking as in deleting a file
                logger.warning(_("Unlinking %r"), self._SESSION_FILE_NEXT)
                os.unlink(self._SESSION_FILE_NEXT, dir_fd=location_fd)
            else:
                # If the write was successful we must flush kernel buffers.
                #
                # We want to be sure this data is really on disk by now as we
                # may crash the machine soon after this method exits.
                logger.debug(
                    # TRANSLATORS: please don't translate fsync()
                    _("Calling fsync() on descriptor %d"), next_session_fd)
                try:
                    os.fsync(next_session_fd)
                except OSError as exc:
                    logger.warning(_("Cannot synchronize file %r: %s"),
                                   self._SESSION_FILE_NEXT, exc)
            finally:
                # Close the new session file
                logger.debug(_("Closing descriptor %d"), next_session_fd)
                os.close(next_session_fd)
            # Rename FILE_NEXT over FILE.
            #
            # Use renameat(2) to ensure that there is no race condition if the
            # location (directory) is being moved
            logger.debug(
                _("Renaming %r to %r"),
                self._SESSION_FILE_NEXT, self._SESSION_FILE)
            try:
                os.rename(self._SESSION_FILE_NEXT, self._SESSION_FILE,
                          src_dir_fd=location_fd, dst_dir_fd=location_fd)
            except Exception as exc:
                # Same as above, if we fail we need to unlink the next file
                # otherwise any other attempts will not be able to open() it
                # with O_EXCL flag.
                logger.warning(
                    _("Unable to rename/overwrite %r to %r: %r"),
                    self._SESSION_FILE_NEXT, self._SESSION_FILE, exc)
                # TRANSLATORS: unlinking as in deleting a file
                logger.warning(_("Unlinking %r"), self._SESSION_FILE_NEXT)
                os.unlink(self._SESSION_FILE_NEXT, dir_fd=location_fd)
            # Flush kernel buffers on the directory.
            #
            # This should ensure the rename operation is really on disk by now.
            # As noted above, this is essential for being able to survive
            # system crash immediately after exiting this method.

            # TRANSLATORS: please don't translate fsync()
            logger.debug(_("Calling fsync() on descriptor %d"), location_fd)
            try:
                os.fsync(location_fd)
            except OSError as exc:
                logger.warning(_("Cannot synchronize directory %r: %s"),
                               self.location, exc)
        finally:
            # Close the location directory
            logger.debug(_("Closing descriptor %d"), location_fd)
            os.close(location_fd)

    def break_lock(self):
        """
        Forcibly unlock the storage by removing a file created during
        atomic filesystem operations of save_checkpoint().

        This method might be useful if save_checkpoint()
        raises LockedStorageError. It removes the "next" file that is used
        for atomic rename.
        """
        _next_session_pathname = os.path.join(
            self.location, self._SESSION_FILE_NEXT)
        logger.debug(
            # TRANSLATORS: unlinking as in deleting a file
            # Please keep the 'next' string untranslated
            _("Forcibly unlinking 'next' file %r"), _next_session_pathname)
        os.unlink(_next_session_pathname)
