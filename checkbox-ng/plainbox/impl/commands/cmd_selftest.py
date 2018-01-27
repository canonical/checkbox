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
:mod:`plainbox.impl.commands.cmd_selftest` -- selftest sub-command
==================================================================
"""
import argparse

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand

__all__ = ['SelfTestCommandBase', 'SelfTestCommand', 'PlainboxSelfTestCommand']


class SelfTestCommandBase(PlainBoxCommand):
    """
    Base class for testing the tool itself

    This base class is shared by two concrete subclasses, the generic
    :class:`SelfTestCommand` and the plainbox-specific
    :class:`PlainboxSelfTestCommand`
    """

    def register_parser(self, subparsers):
        self.parser = subparsers.add_parser(
            "self-test", help=_("run unit and integration tests"),
            prog="%(prog)s self-test")
        self.parser.set_defaults(command=self)
        # Register a number of TextTestRunner options.
        # More items may be added here as the need arises.
        self.parser.add_argument(
            '--fail-fast', default=False, action="store_true",
            help=_("abort the test on first failure"))
        group = self.parser.add_argument_group("verbosity settings")
        group.set_defaults(verbosity=1)
        group.add_argument(
            '-q', '--quiet', dest='verbosity', action="store_const", const=0,
            help=_("run tests quietly"))
        group.add_argument(
            '--normal', dest='verbosity', action="store_const", const=1,
            help=_("run tests with normal verbosity (default)"))
        group.add_argument(
            '-v', '--verbose', dest='verbosity', action="store_const", const=2,
            help=_("run tests verbosely, printing each test case name"))
        self.parser.add_argument(
            '--after-reexec', dest='reexec', action="store_false",
            default=True, help=argparse.SUPPRESS)


class SelfTestCommand(SelfTestCommandBase):

    def __init__(self, suite_loader):
        self.suite_loader = suite_loader

    def invoked(self, ns):
        from plainbox.impl.commands.inv_selftest import SelfTestInvocation
        return SelfTestInvocation(self.suite_loader).run(ns)


class PlainboxSelfTestCommand(SelfTestCommandBase):
    """
    Implementation of the 'plainbox selftest' command
    """

    def register_parser(self, subparsers):
        super().register_parser(subparsers)
        # Add an option that selects either integration tests or unit tests
        group = self.parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-i', '--integration-tests',
            action='store_const',
            dest='test_suite',
            const='plainbox.tests.load_integration_tests',
            help=_("run integration test suite (this verifies checkbox jobs)"))
        group.add_argument(
            '-u', '--unit-tests',
            action='store_const',
            dest='test_suite',
            const='plainbox.tests.load_unit_tests',
            help=_("run unit tests (this only verifies plainbox core)"))
        group.add_argument(
            '-s', '--suite', metavar=_("SUITE"),
            action='store',
            dest='test_suite',
            help=_("run custom test suite"))

    def invoked(self, ns):
        from plainbox.impl.commands.inv_selftest import SelfTestInvocation
        return SelfTestInvocation(ns.test_suite).run(ns)
