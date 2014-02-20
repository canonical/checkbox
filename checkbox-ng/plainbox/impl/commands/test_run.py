# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique  <roadmr@ubuntu.com>
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
plainbox.impl.commands.test_run
===============================

Test definitions for plainbox.impl.run module
"""

import os
import shutil
import tempfile

from collections import OrderedDict
from inspect import cleandoc
from unittest import TestCase

from plainbox.impl.box import main
from plainbox.impl.exporter.json import JSONSessionStateExporter
from plainbox.impl.exporter.rfc822 import RFC822SessionStateExporter
from plainbox.impl.exporter.text import TextSessionStateExporter
from plainbox.impl.exporter.xml import XMLSessionStateExporter
from plainbox.testing_utils.io import TestIO
from plainbox.vendor.mock import patch, Mock


class TestRun(TestCase):

    @patch.dict('sys.modules', {'concurrent': Mock()})
    def setUp(self):
        # session data are kept in XDG_CACHE_HOME/plainbox/.session
        # To avoid resuming a real session, we have to select a temporary
        # location instead
        self._sandbox = tempfile.mkdtemp()
        self._env = os.environ
        os.environ['XDG_CACHE_HOME'] = self._sandbox
        self._exporters = OrderedDict([
            ('json', JSONSessionStateExporter),
            ('rfc822', RFC822SessionStateExporter),
            ('text', TextSessionStateExporter),
            ('xml', XMLSessionStateExporter),
        ])

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
          --not-interactive     skip tests that require interactivity
          -n, --dry-run         don't really run most jobs

        output options:
          -f FORMAT, --output-format FORMAT
                                save test results in the specified FORMAT (pass ? for
                                a list of choices)
          -p OPTIONS, --output-options OPTIONS
                                comma-separated list of options for the export
                                mechanism (pass ? for a list of choices)
          -o FILE, --output-file FILE
                                save test results to the specified FILE (or to stdout
                                if FILE is -)
          -t TRANSPORT, --transport TRANSPORT
                                use TRANSPORT to send results somewhere (pass ? for a
                                list of choices)
          --transport-where WHERE
                                where to send data using the selected transport
          --transport-options OPTIONS
                                comma-separated list of key-value options (k=v) to be
                                passed to the transport

        job definition options:
          -i PATTERN, --include-pattern PATTERN
                                include jobs matching the given regular expression
          -x PATTERN, --exclude-pattern PATTERN
                                exclude jobs matching the given regular expression
          -w WHITELIST, --whitelist WHITELIST
                                load whitelist containing run patterns
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    @patch('plainbox.impl.ctrl.check_output')
    def test_run_without_args(self, mock_check_output):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                with patch('plainbox.impl.commands.run.authenticate_warmup') as mock_warmup:
                    mock_warmup.return_value = 0
                    main(['run'])
            self.assertEqual(call.exception.args, (0,))
        expected1 = """
        ===============================[ Analyzing Jobs ]===============================
        Estimated duration cannot be determined for automated jobs.
        Estimated duration cannot be determined for manual jobs.
        ==============================[ Running All Jobs ]==============================
        ==================================[ Results ]===================================
        """
        expected2 = """
        ===============================[ Authentication ]===============================
        ===============================[ Analyzing Jobs ]===============================
        Estimated duration cannot be determined for automated jobs.
        Estimated duration cannot be determined for manual jobs.
        ==============================[ Running All Jobs ]==============================
        ==================================[ Results ]===================================
        """
        self.assertIn(io.combined, [
            cleandoc(expected1) + "\n",
            cleandoc(expected2) + "\n"])

    def test_output_format_list(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                with patch('plainbox.impl.commands.run.get_all_exporters') as mock_get_all_exporters:
                    mock_get_all_exporters.return_value = self._exporters
                    main(['run', '--output-format=?'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        Available output formats: json, rfc822, text, xml
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_output_option_list(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                with patch('plainbox.impl.commands.run.get_all_exporters') as mock_get_all_exporters:
                    mock_get_all_exporters.return_value = self._exporters
                    main(['run', '--output-option=?'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        Each format may support a different set of options
        json: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments, with-job-via, with-job-hash, machine-json
        rfc822: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments, with-job-via, with-job-hash
        text: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments, with-job-via, with-job-hash
        xml: 
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def tearDown(self):
        shutil.rmtree(self._sandbox)
        os.environ = self._env
