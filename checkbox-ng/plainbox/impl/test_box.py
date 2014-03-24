# This file is part of Checkbox.
#
# Copyright 2012-2013 Canonical Ltd.
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

from inspect import cleandoc
from io import TextIOWrapper
from unittest import TestCase

from plainbox import __version__ as version
from plainbox.abc import IProvider1
from plainbox.impl.box import main
from plainbox.impl.clitools import ToolBase
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.testing_utils import MockJobDefinition, suppress_warnings
from plainbox.testing_utils.io import TestIO
from plainbox.vendor.mock import Mock


def mock_whitelist(name, text, filename):
    """
    Create a mocked whitelist for
    CheckBoxInvocationMixIn._get_matching_job_list(). Specifically
    for ``ns.whitelists`` as passed to that function.

    :param name:
        Name of the mocked object, helps in debugging
    :param text:
        Full text of the whitelist
    :param filename:
        Filename of the whitelist file
    """
    whitelist = Mock(spec=TextIOWrapper, name=name)
    whitelist.name = filename
    whitelist.read.return_value = text
    return whitelist


class MiscTests(TestCase):

    def setUp(self):
        self.job_foo = MockJobDefinition(id='foo')
        self.job_bar = MockJobDefinition(id='bar')
        self.job_baz = MockJobDefinition(id='baz')
        self.provider1 = Mock(IProvider1)
        self.provider1.get_builtin_whitelists.return_value = []
        self.provider_list = [self.provider1]
        self.obj = CheckBoxInvocationMixIn(self.provider_list)

    def test_matching_job_list(self):
        # Nothing gets selected automatically
        ns = Mock(name="ns")
        ns.whitelist = []
        ns.include_pattern_list = []
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [])

    def test_matching_job_list_including(self):
        # Including jobs with glob pattern works
        ns = Mock(name="ns")
        ns.whitelist = []
        ns.include_pattern_list = ['f.+']
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])

    def test_matching_job_list_excluding(self):
        # Excluding jobs with glob pattern works
        ns = Mock(name="ns")
        ns.whitelist = []
        ns.include_pattern_list = ['.+']
        ns.exclude_pattern_list = ['f.+']
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_bar])

    def test_matching_job_list_whitelist(self):
        # whitelists contain list of include patterns
        # that are read and interpreted as usual
        ns = Mock(name="ns")
        ns.whitelist = [
            mock_whitelist("foo_whitelist", "foo", "foo.whitelist")]
        ns.include_pattern_list = []
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])

    def test_matching_job_list_multiple_whitelists(self):
        ns = Mock(name="ns")
        ns.whitelist = [
            mock_whitelist("whitelist_a", "foo", "a.whitelist"),
            mock_whitelist("whitelist_b", "baz", "b.whitelist"),
        ]
        ns.include_pattern_list = []
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar, self.job_baz])
        self.assertEqual(observed, [self.job_foo, self.job_baz])

    def test_no_prefix_matching_including(self):
        # Include patterns should only match whole job name
        ns = Mock(name="ns")
        ns.whitelist = [
            mock_whitelist("whitelist_a", "fo", "a.whitelist"),
            mock_whitelist("whitelist_b", "ba.+", "b.whitelist"),
        ]
        ns.include_pattern_list = ['fo', 'ba.+']
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [self.job_foo,
                                                        self.job_bar])
        self.assertEqual(observed, [self.job_bar])

    def test_no_prefix_matching_excluding(self):
        # Exclude patterns should only match whole job name
        ns = Mock(name="ns")
        ns.whitelist = []
        ns.include_pattern_list = ['.+']
        ns.exclude_pattern_list = ['fo', 'ba.+']
        observed = self.obj._get_matching_job_list(
            ns, [self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])

    def test_invalid_pattern_including(self):
        ns = Mock(name="ns")
        ns.whitelist = []
        ns.include_pattern_list = ['?']
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(
            ns, [self.job_foo, self.job_bar])
        self.assertEqual(observed, [])

    def test_invalid_pattern_excluding(self):
        ns = Mock(name="ns")
        ns.whitelist = []
        ns.include_pattern_list = ['fo.*']
        ns.exclude_pattern_list = ['[bar']
        observed = self.obj._get_matching_job_list(
            ns, [self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])


class TestMain(TestCase):

    def test_version(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--version'])
            self.assertEqual(call.exception.args, (0,))
        self.assertEqual(io.combined, "{}\n".format(
            ToolBase.format_version_tuple(version)))

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
        usage: plainbox [-h] [--version] [--providers {all,stub}] [-v] [-D] [-C]
                        [-T LOGGER] [-P] [-I]
                        {run,self-test,check-config,dev,startprovider} ...

        positional arguments:
          {run,self-test,check-config,dev,startprovider}
            run                 run a test job
            self-test           run unit and integration tests
            check-config        check and display plainbox configuration
            dev                 development commands
            startprovider       create a new provider (directory)

        optional arguments:
          -h, --help            show this help message and exit
          --version             show program's version number and exit

        provider list and development:
          --providers {all,stub}
                                which providers to load

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
        usage: plainbox [-h] [--version] [--providers {all,stub}] [-v] [-D] [-C]
                        [-T LOGGER] [-P] [-I]
                        {run,self-test,check-config,dev,startprovider} ...
        plainbox: error: too few arguments
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")


class TestSpecial(TestCase):

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['dev', 'special', '--help'])
            self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox dev special [-h] (-j | -J | -e | -d) [--dot-resources]
                                    [-i PATTERN] [-x PATTERN] [-w WHITELIST]

        optional arguments:
          -h, --help            show this help message and exit
          -j, --list-jobs       list jobs instead of running them
          -J, --list-job-hashes
                                list jobs with cheksums instead of running them
          -e, --list-expressions
                                list all unique resource expressions
          -d, --dot             print a graph of jobs instead of running them
          --dot-resources       show resource relationships (for --dot)

        job definition options:
          -i PATTERN, --include-pattern PATTERN
                                include jobs matching the given regular expression
          -x PATTERN, --exclude-pattern PATTERN
                                exclude jobs matching the given regular expression
          -w WHITELIST, --whitelist WHITELIST
                                load whitelist containing run patterns
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_without_args(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['dev', 'special'])
            self.assertEqual(call.exception.args, (2,))
        expected = """
        usage: plainbox dev special [-h] (-j | -J | -e | -d) [--dot-resources]
                                    [-i PATTERN] [-x PATTERN] [-w WHITELIST]
        plainbox dev special: error: one of the arguments -j/--list-jobs -J/--list-job-hashes -e/--list-expressions -d/--dot is required
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_list_jobs(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['--providers', 'stub', 'dev', 'special', '--list-jobs'])
            self.assertEqual(call.exception.args, (0,))
        self.assertIn(
            "2013.com.canonical.plainbox::stub/false", io.stdout.splitlines())
        self.assertIn(
            "2013.com.canonical.plainbox::stub/true", io.stdout.splitlines())

    def test_run_list_jobs_with_filtering(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['--providers', 'stub', 'dev', 'special',
                      ('--include-pattern='
                       '2013.com.canonical.plainbox::stub/false'),
                      '--list-jobs'])
            self.assertEqual(call.exception.args, (0,))
        self.assertIn(
            "2013.com.canonical.plainbox::stub/false", io.stdout.splitlines())
        self.assertNotIn(
            "2013.com.canonical.plainbox::stub/true", io.stdout.splitlines())

    def test_run_list_expressions(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['--providers', 'stub', 'dev', 'special', '--list-expressions'])
            self.assertEqual(call.exception.args, (0,))
        self.assertIn(
            'stub_package.name == "checkbox"', io.stdout.splitlines())

    def test_run_dot(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['--providers', 'stub', 'dev', 'special', '--dot'])
            self.assertEqual(call.exception.args, (0,))
        self.assertIn(
            '\t"2013.com.canonical.plainbox::stub/true" [];',
            io.stdout.splitlines())
        # Do basic graph checks
        self._check_digraph_sanity(io)

    def test_run_dot_with_resources(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['--providers', 'stub', 'dev', 'special', '--dot',
                      '--dot-resources'])
            self.assertEqual(call.exception.args, (0,))
        self.assertIn(
            '\t"2013.com.canonical.plainbox::stub/true" [];', io.stdout.splitlines())
        self.assertIn(
            ('\t"2013.com.canonical.plainbox::stub/requirement/good" -> '
             '"2013.com.canonical.plainbox::stub_package" [style=dashed, label'
             '="stub_package.name == \'checkbox\'"];'),
            io.stdout.splitlines())
        # Do basic graph checks
        self._check_digraph_sanity(io)

    def _check_digraph_sanity(self, io):
        # Ensure that all lines inside the graph are terminated with a
        # semicolon
        for line in io.stdout.splitlines()[1:-2]:
            self.assertTrue(line.endswith(';'))
        # Ensure that graph header and footer are there
        self.assertEqual("digraph dependency_graph {",
                         io.stdout.splitlines()[0])
        self.assertEqual("}", io.stdout.splitlines()[-1])
