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
from shutil import copyfileobj
from shutil import make_archive
import io
import itertools
import os
import sys

from plainbox.i18n import gettext as _
from plainbox.impl.applogic import get_all_exporter_names
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.session import SessionManager
from plainbox.impl.session import SessionPeekHelper
from plainbox.impl.session import SessionResumeError
from plainbox.impl.session import SessionStorageRepository


logger = getLogger("plainbox.commands.session")


class SessionInvocation:
    """
    Invocation of the 'plainbox session' command.

    :ivar ns:
        The argparse namespace obtained from SessionCommand
    """

    def __init__(self, ns, provider_loader):
        self.ns = ns
        self.provider_loader = provider_loader

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
        elif cmd == 'export':
            self.export_session()

    def list_sessions(self):
        repo = SessionStorageRepository()
        storage = None
        for storage in repo.get_storage_list():
            if self.ns.only_ids:
                print(storage.id)
                continue
            data = storage.load_checkpoint()
            if len(data) > 0:
                metadata = SessionPeekHelper().peek(data)
                print(_("session {0} app:{1}, flags:{2!r}, title:{3!r}")
                      .format(storage.id, metadata.app_id,
                              sorted(metadata.flags), metadata.title))
            else:
                print(_("session {0} (not saved yet)").format(storage.id))
        if not self.ns.only_ids and storage is None:
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
                if self.ns.resume:
                    print(_("Resuming session {0} ...").format(storage.id))
                    try:
                        self.resume_session(storage)
                    except SessionResumeError as exc:
                        print(_("Failed to resume session:"), exc)
                    else:
                        print(_("session resumed successfully"))

    def resume_session(self, storage):
        return SessionManager.load_session(
            self._get_all_units(), storage, flags=self.ns.flag)

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

    def export_session(self):
        if self.ns.output_format == _('?'):
            self._print_output_format_list()
            return 0
        elif self.ns.output_options == _('?'):
            self._print_output_option_list()
            return 0
        storage = self._lookup_storage(self.ns.session_id)
        if storage is None:
            print(_("No such session: {0}").format(self.ns.session_id))
        else:
            print(_("Exporting session..."))
            manager = SessionManager.load_session(
                self._get_all_units(), storage, flags=self.ns.flag)
            exporter = self._create_exporter(manager)
            # Get a stream with exported session data.
            exported_stream = io.BytesIO()
            exporter.dump_from_session_manager(manager, exported_stream)
            exported_stream.seek(0)  # Need to rewind the file, puagh
            # Write the stream to file if requested
            if self.ns.output_file is sys.stdout:
                # This requires a bit more finesse, as exporters output bytes
                # and stdout needs a string.
                translating_stream = ByteStringStreamTranslator(
                    self.ns.output_file, "utf-8")
                copyfileobj(exported_stream, translating_stream)
            else:
                print(_("Saving results to {}").format(
                    self.ns.output_file.name))
                copyfileobj(exported_stream, self.ns.output_file)
            if self.ns.output_file is not sys.stdout:
                self.ns.output_file.close()

    def _get_all_units(self):
        return list(
            itertools.chain(*[p.unit_list for p in self.provider_loader()]))

    def _print_output_format_list(self):
        print(_("Available output formats: {}").format(
            ', '.join(get_all_exporter_names())))

    def _print_output_option_list(self):
        print(_("Each format may support a different set of options"))
        with SessionManager.get_throwaway_manager() as manager:
            for name, exporter in manager.exporter_map.items():
                print("{}: {}".format(
                    name, ", ".join(exporter.exporter_cls.supported_option_list)))

    def _create_exporter(self, manager):
        if self.ns.output_options:
            option_list = self.ns.output_options.split(',')
        else:
            option_list = None
        return manager.create_exporter(self.ns.output_format, option_list)

    def _lookup_storage(self, session_id):
        repo = SessionStorageRepository()
        for storage in repo.get_storage_list():
            if storage.id == session_id:
                return storage
