# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique  <roadmr@ubuntu.com>
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
plainbox.impl.commands.test_run
===============================

Test definitions for plainbox.impl.run module
"""

import os
import shutil
import tempfile

from inspect import cleandoc
from mock import patch
from unittest import TestCase

from plainbox.impl.box import main
from plainbox.testing_utils.io import TestIO


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
                with patch('plainbox.impl.commands.run.authenticate_warmup') as mock_warmup:
                    mock_warmup.return_value = 0
                    main(['run'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        ===============================[ Authentication ]===============================
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
