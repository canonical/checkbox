# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.commands.crash` -- crash sub-command
========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging

from plainbox.impl.commands import PlainBoxCommand


logger = logging.getLogger("plainbox.commands.crash")


class CrashInvocation:

    def __init__(self, ns):
        self.ns = ns

    def run(self):
        if self.ns.action == 'crash':
            raise Exception("crashing as requested")
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
            "crash", help="crash the application")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-c', '--crash',
            dest='action',
            action='store_const',
            const='crash',
            help='Raise an exception')
        group.add_argument(
            '-H', '--hang',
            dest='action',
            action='store_const',
            const='hang',
            help='Hang the application with a busy loop')
        parser.set_defaults(command=self)
