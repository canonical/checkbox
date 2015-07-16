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
:mod:`plainbox.impl.commands.cmd_session` -- run sub-command
============================================================
"""
from argparse import FileType

from plainbox.i18n import docstring
from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.applogic import get_all_exporter_names
from plainbox.impl.commands import PlainBoxCommand


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

    def __init__(self, provider_loader):
        super().__init__()
        self.provider_loader = provider_loader

    def invoked(self, ns):
        from plainbox.impl.commands.inv_session import SessionInvocation
        return SessionInvocation(ns, self.provider_loader).run()

    def register_parser(self, subparsers):
        parser = self.add_subcommand(subparsers)
        parser.prog = 'plainbox session'
        parser.set_defaults(default_session_cmd='list')
        # Duplicate the default value of --only-ids This is only used when
        # we use the default command aka when 'plainbox session' runs.
        parser.set_defaults(only_ids=False)
        session_subparsers = parser.add_subparsers(
            title=_('available session subcommands'))
        list_parser = session_subparsers.add_parser(
            'list', help=_('list available sessions'))
        list_parser.add_argument(
            '--only-ids', help=_('print one id per line only'),
            action='store_true', default=False)
        list_parser.set_defaults(session_cmd='list')
        remove_parser = session_subparsers.add_parser(
            'remove', help=_('remove one more more sessions'))
        remove_parser.add_argument(
            'session_id_list', metavar=_('SESSION-ID'), nargs="+",
            help=_('Identifier of the session to remove'))
        remove_parser.set_defaults(session_cmd='remove')
        show_parser = session_subparsers.add_parser(
            'show', help=_('show a single session'))
        show_parser.add_argument(
            'session_id_list', metavar=_('SESSION-ID'), nargs="+",
            help=_('Identifier of the session to show'))
        show_parser.add_argument(
            '-r', '--resume', action='store_true',
            help=_("resume the session (useful for debugging)"))
        show_parser.add_argument(
            '-f', '--flag', action='append', metavar=_("FLAG"),
            help=_("pass this resume flag to the session resume code"))
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
        export_parser = session_subparsers.add_parser(
            'export', help=_('export a single session'))
        export_parser.add_argument(
            'session_id', metavar=_('SESSION-ID'),
            help=_('Identifier of the session to export'))
        export_parser.add_argument(
            '--flag', action='append', metavar=_("FLAG"),
            help=_("pass this resume flag to the session resume code"))
        export_parser.set_defaults(session_cmd='export')
        group = export_parser.add_argument_group(_("output options"))
        group.add_argument(
            '-f', '--output-format', default='text',
            metavar=_('FORMAT'), choices=[_('?')] + get_all_exporter_names(),
            help=_('save test results in the specified FORMAT'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '-p', '--output-options', default='',
            metavar=_('OPTIONS'),
            help=_('comma-separated list of options for the export mechanism'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '-o', '--output-file', default='-',
            metavar=_('FILE'), type=FileType("wb"),
            help=_('save test results to the specified FILE'
                   ' (or to stdout if FILE is -)'))
