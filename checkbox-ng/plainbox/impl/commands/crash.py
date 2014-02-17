# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.commands.crash` -- crash sub-command
========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand


logger = logging.getLogger("plainbox.commands.crash")


class CrashInvocation:

    def __init__(self, ns):
        self.ns = ns

    def run(self):
        if self.ns.action == 'crash':
            raise Exception(_("crashing as requested"))
        elif self.ns.action == 'hang':
            while True:
                pass


class CrashCommand(PlainBoxCommand):
    """
    Implementation of ``$ plainbox dev crash``
    """

    def invoked(self, ns):
        return CrashInvocation(ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "crash", help=_("crash the application"))
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-c', '--crash',
            dest='action',
            action='store_const',
            const='crash',
            help=_('Raise an exception'))
        group.add_argument(
            '-H', '--hang',
            dest='action',
            action='store_const',
            const='hang',
            help=_('Hang the application with a busy loop'))
        parser.set_defaults(command=self)
