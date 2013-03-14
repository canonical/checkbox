# This file is part of Checkbox.
#
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
:mod:`plainbox.impl.commands.sru` -- sru sub-command
====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from plainbox.impl.commands import PlainBoxCommand


class SRUCommand(PlainBoxCommand):
    """
    Command for running Stable Release Update (SRU) tests.

    Stable release updates are periodic fixes for nominated bugs that land in
    existing supported Ubuntu releases. To ensure a certain level of quality
    all SRU updates affecting hardware enablement are automatically tested
    on a pool of certified machines.

    This command is _temporary_ and will eventually migrate to the checkbox
    side. Its intended lifecycle is for the development and validation of
    plainbox core on realistic workloads.
    """

    def invoked(self, ns):
        # a list of todos from functionality point of view:
        # TODO: load "sru" whitelist from checkbox
        # TODO: run all tests in implicit batch/noninteractive mode
        # TODO: instantiate the xml exporter
        # TODO: instantiate the 'c4' transport/stream wrapper
        # TODO: try sending stuff to c4
        # TODO: if that fails save the result on disk and bail
        # a list of todos from implementation point of view:
        # TODO: refactor box.py so that running tests with simple
        #       gui is a reusable component that can be used both
        #       for 'sru' and 'run' command.
        # TODO: update docs on sru command
        print("This command is currently not implemented")
        return 1

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "sru", help="run automated stable release update tests")
        parser.set_defaults(command=self)
        parser.add_argument(
            'secure_id', metavar="SECURE-ID",
            action='store',
            help=("Associate submission with a machine using this SECURE-ID"))
        parser.add_argument(
            'fallback_file', metavar="FALLBACK-FILE",
            action='store',
            help=("If submission fails save the test report as FALLBACK-FILE"))
        parser.add_argument(
            '--destination', metavar="URL",
            action='store',
            default="https://certification.canonical.com/submissions/submit/",
            help=("POST the test report XML to this URL"))
