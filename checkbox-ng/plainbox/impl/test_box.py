# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
plainbox.impl.test_box
======================

Test definitions for plainbox.impl.box module
"""
from collections import defaultdict
from inspect import cleandoc
from io import TextIOWrapper
from unittest import TestCase
import warnings

from plainbox import __version__ as version
from plainbox.abc import IProvider1
from plainbox.impl.box import main
from plainbox.impl.box import stubbox_main
from plainbox.impl.clitools import ToolBase
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.testing_utils import MockJobDefinition, suppress_warnings
from plainbox.testing_utils.io import TestIO
from plainbox.vendor.mock import Mock


def setUpModule():
    warnings.filterwarnings(
        'ignore', 'validate is deprecated since version 0.11')


def tearDownModule():
    warnings.resetwarnings()


class MiscTests(TestCase):

    def setUp(self):
        self.provider1 = Mock(spec=IProvider1)
        self.job_foo = MockJobDefinition(id='foo', provider=self.provider1)
        self.job_bar = MockJobDefinition(id='bar', provider=self.provider1)
        self.job_baz = MockJobDefinition(id='baz', provider=self.provider1)
        self.provider1.id_map = defaultdict(
            list, foo=[self.job_foo], bar=[self.job_bar], baz=[self.job_baz])
        self.provider1.unit_list = [self.job_foo, self.job_bar, self.job_baz]
        self.config = Mock(name='config')
        self.provider_loader = lambda: [self.provider1]
        self.obj = CheckBoxInvocationMixIn(self.provider_loader, self.config)

    def test_matching_job_list(self):
        # Nothing gets selected automatically
        ns = Mock(name="ns")
        ns.include_pattern_list = []
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [])

    def test_matching_job_list_including(self):
        # Including jobs with glob pattern works
        ns = Mock(name="ns")
        ns.include_pattern_list = ['f.+']
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])

    def test_matching_job_list_excluding(self):
        # Excluding jobs with glob pattern works
        ns = Mock(name="ns")
        ns.include_pattern_list = ['.+']
        ns.exclude_pattern_list = ['f.+']
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_bar])

    def test_no_prefix_matching_excluding(self):
        # Exclude patterns should only match whole job name
        ns = Mock(name="ns")
        ns.include_pattern_list = ['.+']
        ns.exclude_pattern_list = ['fo', 'ba.+']
        observed = self.obj._get_matching_job_list(
            ns, [self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])

    def test_invalid_pattern_including(self):
        ns = Mock(name="ns")
        ns.include_pattern_list = ['\?']
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(
            ns, [self.job_foo, self.job_bar])
        self.assertEqual(observed, [])

    def test_invalid_pattern_excluding(self):
        ns = Mock(name="ns")
        ns.include_pattern_list = ['fo.*']
        ns.exclude_pattern_list = ['\[bar']
        observed = self.obj._get_matching_job_list(
            ns, [self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])


class TestMain(TestCase):

    def test_version(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                stubbox_main(['--version'])
            self.assertEqual(call.exception.args, (0,))
        self.assertEqual(io.combined, "{}\n".format(version))

    @suppress_warnings
    # Temporarily supress warnings (i.e. ResourceWarning) to work around
    # Issue #341 in distribute (< 0.6.33).
    # See: https://bitbucket.org/tarek/distribute/issue/341
    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--help'])
        self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox [--help] [--version] | [options] <command> ...

        positional arguments:
          {run,session,dev,startprovider}
            run                 run a test job
            session             session management commands
            dev                 development commands
            startprovider       create a new provider (directory)

        optional arguments:
          -h, --help            show this help message and exit
          --version             show program's version number and exit

        logging and debugging:
          -v, --verbose         be more verbose (same as --log-level=INFO)
          -D, --debug           enable DEBUG messages on the root logger
          -C, --debug-console   display DEBUG messages in the console
          -T LOGGER, --trace LOGGER
                                enable DEBUG messages on the specified logger (can be
                                used multiple times)
          -P, --pdb             jump into pdb (python debugger) when a command crashes
          -I, --debug-interrupt
                                crash on SIGINT/KeyboardInterrupt, useful with --pdb

        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_without_args(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main([])
            self.assertEqual(call.exception.args, (2,))
        expected = """
        usage: plainbox [--help] [--version] | [options] <command> ...
        plainbox: error: too few arguments
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")
