# This file is part of Checkbox.
#
# Copyright 2012-2013 Canonical Ltd.
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
plainbox.impl.test_box
======================

Test definitions for plainbox.impl.box module
"""

import os
import shutil
import tempfile

from inspect import cleandoc
from mock import Mock
from unittest import TestCase

from plainbox import __version__ as version
from plainbox.impl.box import main
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.mock_job import MockJobDefinition
from plainbox.testing_utils.io import TestIO


class MiscTests(TestCase):

    def setUp(self):
        self.job_foo = MockJobDefinition(name='foo')
        self.job_bar = MockJobDefinition(name='bar')
        self.obj = CheckBoxCommandMixIn(Mock(name="checkbox"))

    def test_matching_job_list(self):
        # Nothing gets selected automatically
        ns = Mock()
        ns.whitelist = None
        ns.include_pattern_list = []
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [])

    def test_matching_job_list_including(self):
        # Including jobs with glob pattern works
        ns = Mock()
        ns.whitelist = None
        ns.include_pattern_list = ['f.+']
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])

    def test_matching_job_list_excluding(self):
        # Excluding jobs with glob pattern works
        ns = Mock()
        ns.whitelist = None
        ns.include_pattern_list = ['.+']
        ns.exclude_pattern_list = ['f.+']
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_bar])

    def test_matching_job_list_whitelist(self):
        # whitelists contain list of include patterns
        # that are read and interpreted as usual
        whitelist = Mock()
        whitelist.readlines.return_value = ['foo']
        ns = Mock()
        ns.whitelist = whitelist
        ns.include_pattern_list = []
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [
            self.job_foo, self.job_bar])
        self.assertEqual(observed, [self.job_foo])

    def test_no_prefix_matching_including(self):
        # Include patterns should only match whole job name
        ns = Mock()
        ns.whitelist = None
        ns.include_pattern_list = ['fo', 'ba.+']
        ns.exclude_pattern_list = []
        observed = self.obj._get_matching_job_list(ns, [self.job_foo,
                                                        self.job_bar])
        self.assertEqual(observed, [self.job_bar])

    def test_no_prefix_matching_excluding(self):
        # Exclude patterns should only match whole job name
        ns = Mock()
        ns.whitelist = None
        ns.include_pattern_list = ['.+']
        ns.exclude_pattern_list = ['fo', 'ba.+']
        observed = self.obj._get_matching_job_list(ns, [self.job_foo,
                                                        self.job_bar])
        self.assertEqual(observed, [self.job_foo])


class TestMain(TestCase):

    def test_version(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--version'])
            self.assertEqual(call.exception.args, (0,))
        self.assertEqual(io.combined, "{}.{}.{}\n".format(*version[:3]))

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--help'])
        self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox [-h] [-v] {run,special,self-test,sru} ...

        positional arguments:
          {run,special,self-test,sru}
            run                 run a test job
            special             special/internal commands
            self-test           run integration tests
            sru                 run automated stable release update tests

        optional arguments:
          -h, --help            show this help message and exit
          -v, --version         show program's version number and exit
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_without_args(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main([])
            self.assertEqual(call.exception.args, (2,))
        expected = """
        usage: plainbox [-h] [-v] {run,special,self-test,sru} ...
        plainbox: error: too few arguments
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")


class TestSpecial(TestCase):

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['special', '--help'])
            self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox special [-h] (-j | -e | -d) [--dot-resources] [-i PATTERN]
                                [-x PATTERN] [-w WHITELIST]

        optional arguments:
          -h, --help            show this help message and exit
          -j, --list-jobs       List jobs instead of running them
          -e, --list-expressions
                                List all unique resource expressions
          -d, --dot             Print a graph of jobs instead of running them
          --dot-resources       Render resource relationships (for --dot)

        job definition options:
          -i PATTERN, --include-pattern PATTERN
                                Run jobs matching the given regular expression.
                                Matches from the start to the end of the line.
          -x PATTERN, --exclude-pattern PATTERN
                                Do not run jobs matching the given regular expression.
                                Matches from the start to the end of the line.
          -w WHITELIST, --whitelist WHITELIST
                                Load whitelist containing run patterns
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_without_args(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['special'])
            self.assertEqual(call.exception.args, (2,))
        expected = """
        usage: plainbox special [-h] (-j | -e | -d) [--dot-resources] [-i PATTERN]
                                [-x PATTERN] [-w WHITELIST]
        plainbox special: error: one of the arguments -j/--list-jobs -e/--list-expressions -d/--dot is required
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_list_jobs(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['special', '--list-jobs'])
            self.assertEqual(call.exception.args, (0,))
        # This is pretty shoddy, ideally we'd load a special job and test for
        # that but it's something that keeps the test more valid than
        # otherwise.
        self.assertIn("mediacard/mmc-insert", io.stdout.splitlines())
        self.assertIn("usb3/insert", io.stdout.splitlines())
        self.assertIn("usb/insert", io.stdout.splitlines())

    def test_run_list_jobs_with_filtering(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['special', '--include-pattern=usb3.+', '--list-jobs'])
            self.assertEqual(call.exception.args, (0,))
        # Test that usb3 insertion test was listed but the usb (2.0) test was not
        self.assertIn("usb3/insert", io.stdout.splitlines())
        self.assertNotIn("usb/insert", io.stdout.splitlines())

    def test_run_list_expressions(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['special', '--list-expressions'])
            self.assertEqual(call.exception.args, (0,))
        # See comment in test_run_list_jobs
        self.assertIn("package.name == 'samba'", io.stdout.splitlines())

    def test_run_dot(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['special', '--dot'])
            self.assertEqual(call.exception.args, (0,))
        # See comment in test_run_list_jobs
        self.assertIn('\t"usb/insert" [color=orange];', io.stdout.splitlines())
        # Do basic graph checks
        self._check_digraph_sanity(io)

    def test_run_dot_with_resources(self):
        with TestIO() as io:
            with self.assertRaises(SystemExit) as call:
                main(['special', '--dot', '--dot-resources'])
            self.assertEqual(call.exception.args, (0,))
        # See comment in test_run_list_jobs
        self.assertIn(
            '\t"usb/insert" [color=orange];', io.stdout.splitlines())
        self.assertIn(
            '\t"daemons/smbd" -> "package" [style=dashed, label="package.name == \'samba\'"];',
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


class TestRun(TestCase):

    def setUp(self):
        # session data are kept in XDG_CACHE_HOME/plainbox/.session
        # To avoid resuming a real session, we have to select a temporary
        # location instead
        self._sandbox = tempfile.mkdtemp()
        self._env = os.environ
        os.environ['XDG_CACHE_HOME'] = self._sandbox

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['run', '--help'])
            self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox run [-h] [--not-interactive] [-n] [-f FORMAT] [-p OPTIONS]
                            [-o FILE] [-t TRANSPORT] [--transport-where WHERE]
                            [--transport-options OPTIONS] [-i PATTERN] [-x PATTERN]
                            [-w WHITELIST]

        optional arguments:
          -h, --help            show this help message and exit

        user interface options:
          --not-interactive     Skip tests that require interactivity
          -n, --dry-run         Don't actually run any jobs

        output options:
          -f FORMAT, --output-format FORMAT
                                Save test results in the specified FORMAT (pass ? for
                                a list of choices)
          -p OPTIONS, --output-options OPTIONS
                                Comma-separated list of options for the export
                                mechanism (pass ? for a list of choices)
          -o FILE, --output-file FILE
                                Save test results to the specified FILE (or to stdout
                                if FILE is -)
          -t TRANSPORT, --transport TRANSPORT
                                use TRANSPORT to send results somewhere (pass ? for a
                                list of choices)
          --transport-where WHERE
                                Where to send data using the selected transport. This
                                is passed as-is and is transport-dependent.
          --transport-options OPTIONS
                                Comma-separated list of key-value options (k=v) to be
                                passed to the transport.

        job definition options:
          -i PATTERN, --include-pattern PATTERN
                                Run jobs matching the given regular expression.
                                Matches from the start to the end of the line.
          -x PATTERN, --exclude-pattern PATTERN
                                Do not run jobs matching the given regular expression.
                                Matches from the start to the end of the line.
          -w WHITELIST, --whitelist WHITELIST
                                Load whitelist containing run patterns
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_run_without_args(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['run'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        ===============================[ Analyzing Jobs ]===============================
        ==============================[ Running All Jobs ]==============================
        ==================================[ Results ]===================================
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_output_format_list(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['run', '--output-format=?'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        Available output formats: json, rfc822, text, xml
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_output_option_list(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['run', '--output-option=?'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        Each format may support a different set of options
        json: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments, machine-json
        rfc822: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments
        text: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments
        xml: 
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def tearDown(self):
        shutil.rmtree(self._sandbox)
        os.environ = self._env
