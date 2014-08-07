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
import argparse
import os
import sys
from unittest.runner import TextTestRunner

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.tests import load_integration_tests, load_unit_tests


class SelfTestCommand(PlainBoxCommand):
    """
    Command for various QA efforts on plainbox and checkbox itself.
    """

    def __init__(self, suite_loader):
        self.suite_loader = suite_loader

    def _reexec_without_locale(self):
        os.environ['LANG'] = ''
        os.environ['LANGUAGE'] = ''
        os.environ['LC_ALL'] = 'C.UTF-8'
        sys.argv.insert(2, '--after-reexec')
        os.execvpe(sys.argv[0], sys.argv, os.environ)

    def invoked(self, ns):
        # If asked to, re-execute without locale
        if ns.reexec:
            self._reexec_without_locale()
        tests = self.suite_loader()
        # Use standard unittest runner, it has somewhat annoying way of
        # displaying test progress but is well-known and will do for now.
        runner = TextTestRunner(verbosity=ns.verbosity, failfast=ns.fail_fast)
        result = runner.run(tests)
        # Forward the successfulness of the test suite as the exit code
        return 0 if result.wasSuccessful() else 1

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


class PlainboxSelfTestCommand(SelfTestCommand):
    """
    Command that distincts between running unit-tests and integrtion tests
    """

    def __init__(self):
        super().__init__(None)

    def register_parser(self, subparsers):
        super().register_parser(subparsers)
        # Add an option that selects either integration tests or unit tests
        group = self.parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-i', '--integration-tests',
            action='store_const',
            dest='suite_loader',
            const=load_integration_tests,
            help=_("run integration test suite (this verifies checkbox jobs)"))
        group.add_argument(
            '-u', '--unit-tests',
            action='store_const',
            dest='suite_loader',
            const=load_unit_tests,
            help=_("run unit tests (this only verifies plainbox core)"))

    def invoked(self, ns):
        self.suite_loader = ns.suite_loader
        super().invoked(ns)
