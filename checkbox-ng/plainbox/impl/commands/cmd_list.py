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
:mod:`plainbox.impl.commands.cmd_list` -- list sub-command
==========================================================
"""
from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand


class ListCommand(PlainBoxCommand):
    """
    Implementation of ``$ plainbox dev list <object>``
    """

    def __init__(self, provider_loader):
        self.provider_loader = provider_loader

    def invoked(self, ns):
        from plainbox.impl.commands.inv_list import ListInvocation
        self.autopager()
        return ListInvocation(self.provider_loader, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "list", help=_("list and describe various objects"),
            prog="plainbox dev list")
        parser.add_argument(
            '-a', '--attrs', default=False, action="store_true",
            help=_("show object attributes"))
        parser.add_argument(
            'group', nargs='?',
            help=_("list objects from the specified group"))
        parser.set_defaults(command=self)
