# This file is part of Checkbox.
#
#
# Copyright 2012 Canonical Ltd.
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
:mod:`plainbox.impl.commands.selftest` -- selftest sub-command
==============================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
from unittest.runner import TextTestRunner

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.tests import load_integration_tests, load_unit_tests


class SelfTestCommand(PlainBoxCommand):
    """
    Command for various QA efforts on plainbox and checkbox itself.

    Currently allows to run integration tests on a installed (or development)
    instance of plainbox.
    """

    def invoked(self, ns):
        # Load tests selected on command line
        tests = ns.suite_loader()
        # Use standard unittest runner, it has somewhat annoying way of
        # displaying test progress but is well-known and will do for now.
        runner = TextTestRunner(verbosity=ns.verbosity, failfast=ns.fail_fast)
        result = runner.run(tests)
        # Forward the successfulness of the test suite as the exit code
        return 0 if result.wasSuccessful() else 1

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "self-test", help=_("run integration tests"))
        parser.set_defaults(command=self)
        # Add an option that selects either integration tests or unit tests
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-i', '--integration-tests',
            action='store_const',
            dest='suite_loader',
            const=load_integration_tests,
            help=_("Run integration test suite (this verifies checkbox jobs)"))
        group.add_argument(
            '-u', '--unit-tests',
            action='store_const',
            dest='suite_loader',
            const=load_unit_tests,
            help=_("Run unit tests (this only verifies plainbox core)"))
        # Register a number of TextTestRunner options.
        # More items may be added here as the need arises.
        parser.add_argument(
            '--fail-fast', default=False, action="store_true",
            help=_("abort the test on first failure"))
        group = parser.add_argument_group("verbosity settings")
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
