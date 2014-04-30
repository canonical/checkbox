# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.commands.session` -- run sub-command
========================================================
"""
from base64 import b64encode
from logging import getLogger
from shutil import make_archive
import os

from plainbox.i18n import docstring
from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.session import SessionStorageRepository
from plainbox.impl.session import SessionPeekHelper


logger = getLogger("plainbox.commands.session")


class SessionInvocation:
    """
    Invocation of the 'plainbox session' command.

    :ivar ns:
        The argparse namespace obtained from SessionCommand
    """

    def __init__(self, ns):
        self.ns = ns

    def run(self):
        cmd = getattr(self.ns, 'session_cmd', self.ns.default_session_cmd)
        if cmd == 'list':
            self.list_sessions()
        elif cmd == 'remove':
            self.remove_session()
        elif cmd == 'show':
            self.show_session()
        elif cmd == 'archive':
            self.archive_session()

    def list_sessions(self):
        repo = SessionStorageRepository()
        storage = None
        for storage in repo.get_storage_list():
            data = storage.load_checkpoint()
            if len(data) > 0:
                metadata = SessionPeekHelper().peek(data)
                print(_("session {0} app:{1}, flags:{2!r}, title:{3!r}")
                      .format(storage.id, metadata.app_id,
                              sorted(metadata.flags), metadata.title))
            else:
                print(_("session {0} (not saved yet)").format(storage.id))
        if storage is None:
            print(_("There are no stored sessions"))

    def remove_session(self):
        for session_id in self.ns.session_id_list:
            storage = self._lookup_storage(session_id)
            if storage is None:
                print(_("No such session"), session_id)
            else:
                storage.remove()
                print(_("Session removed"), session_id)

    def show_session(self):
        for session_id in self.ns.session_id_list:
            storage = self._lookup_storage(session_id)
            if storage is None:
                print(_("No such session"), session_id)
            else:
                print("[{}]".format(session_id))
                print(_("location:"), storage.location)
                data = storage.load_checkpoint()
                if len(data) == 0:
                    continue
                metadata = SessionPeekHelper().peek(data)
                print(_("application ID: {0!r}").format(metadata.app_id))
                print(_("application-specific blob: {0}").format(
                    b64encode(metadata.app_blob).decode('ASCII')
                    if metadata.app_blob is not None else None))
                print(_("session title: {0!r}").format(metadata.title))
                print(_("session flags: {0!r}").format(sorted(metadata.flags)))
                print(_("current job ID: {0!r}").format(
                    metadata.running_job_name))
                print(_("data size: {0}").format(len(data)))

    def archive_session(self):
        session_id = self.ns.session_id
        storage = self._lookup_storage(session_id)
        if storage is None:
            print(_("No such session: {0}").format(self.ns.session_id))
        else:
            print(_("Archiving session..."))
            archive = make_archive(
                self.ns.archive, 'gztar',
                os.path.dirname(storage.location),
                os.path.basename(storage.location))
            print(_("Created archive: {0}").format(archive))

    def _lookup_storage(self, session_id):
        repo = SessionStorageRepository()
        for storage in repo.get_storage_list():
            if storage.id == session_id:
                return storage


@docstring(
    N_("""
    session management commands

    This command can be used to list, show and remove sessions owned by the
    current user.

    @EPILOG@

    Each session has a small amount of meta-data that is available for
    inspection. Each session has an application identifier (set by the
    application that created that session), a title, that is human readable
    piece of text that helps to distinguish sessions, and a set of flags.

    Flags are particularly useful for determining what is the overall state
    of any particular session. Two flags are standardized (other flags can be
    used by applications): incomplete and submitted. The 'incomplete' flag is
    removed after all desired jobs have been executed. The 'submitted' flag
    is set after a submission is made using any of the transport mechanisms.
    """))
class SessionCommand(PlainBoxCommand):

    def invoked(self, ns):
        return SessionInvocation(ns).run()

    def register_parser(self, subparsers):
        parser = self.add_subcommand(subparsers)
        parser.set_defaults(default_session_cmd='list')
        session_subparsers = parser.add_subparsers(
            title=_('available session subcommands'))
        list_parser = session_subparsers.add_parser(
            'list', help=_('list available sessions'))
        list_parser.set_defaults(session_cmd='list')
        remove_parser = session_subparsers.add_parser(
            'remove', help=_('remove a session'))
        remove_parser.add_argument(
            'session_id_list', metavar=_('SESSION-ID'), nargs="+",
            help=_('Identifier of the session to remove'))
        remove_parser.set_defaults(session_cmd='remove')
        show_parser = session_subparsers.add_parser(
            'show', help=_('show a single session'))
        show_parser.add_argument(
            'session_id_list', metavar=_('SESSION-ID'), nargs="+",
            help=_('Identifier of the session to show'))
        show_parser.set_defaults(session_cmd='show')
        archive_parser = session_subparsers.add_parser(
            'archive', help=_('archive a single session'))
        archive_parser.add_argument(
            'session_id', metavar=_('SESSION-ID'),
            help=_('Identifier of the session to archive'))
        archive_parser.add_argument(
            'archive', metavar=_('ARCHIVE'),
            help=_('Name of the archive to create'))
        archive_parser.set_defaults(session_cmd='archive')
