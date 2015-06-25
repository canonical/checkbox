# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
import warnings

from collections import OrderedDict
from inspect import cleandoc
from unittest import TestCase

from plainbox.impl.box import main
from plainbox.impl.exporter.json import JSONSessionStateExporter
from plainbox.impl.exporter.rfc822 import RFC822SessionStateExporter
from plainbox.impl.exporter.text import TextSessionStateExporter
from plainbox.testing_utils.io import TestIO
from plainbox.vendor.mock import patch, Mock


class TestRun(TestCase):

    @patch.dict('sys.modules', {'concurrent': Mock()})
    def setUp(self):
        warnings.filterwarnings(
            'ignore', 'validate is deprecated since version 0.11')
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
        usage: plainbox run [-h] [--non-interactive] [-n] [--dont-suppress-output]
                            [-f FORMAT] [-p OPTIONS] [-o FILE] [-t TRANSPORT]
                            [--transport-where WHERE] [--transport-options OPTIONS]
                            [-T TEST-PLAN-ID] [-i PATTERN] [-x PATTERN] [-w WHITELIST]

        optional arguments:
          -h, --help            show this help message and exit

        user interface options:
          --non-interactive     skip tests that require interactivity
          -n, --dry-run         don't really run most jobs
          --dont-suppress-output
                                don't suppress the output of certain job plugin types

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

        test selection options:
          -T TEST-PLAN-ID, --test-plan TEST-PLAN-ID
                                load the specified test plan
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
                main(['run', '--no-color'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        ===============================[ Analyzing Jobs ]===============================
        =============================[ Session Statistics ]=============================
        This session is about 0.00% complete
        Estimated duration cannot be determined for automated jobs.
        Estimated duration cannot be determined for manual jobs.
        Size of the desired job list: 0
        Size of the effective execution plan: 0
        ===========================[ Running Selected Jobs ]============================
        ==================================[ Results ]===================================
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_output_format_list(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['run', '--output-format=?'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        Available output formats:
        2013.com.canonical.plainbox::hexr - Generate XML (for certification)
        2013.com.canonical.plainbox::html - Generate a standalone HTML
        2013.com.canonical.plainbox::json - Generate JSON output
        2013.com.canonical.plainbox::rfc822 - Generate RCF822 output
        2013.com.canonical.plainbox::text - Generate plain text output
        2013.com.canonical.plainbox::xlsx - Generate an Excel 2007+ XLSX document
        """
        self.assertIn(cleandoc(expected) + "\n", io.combined)

    def test_output_option_list(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['run', '--output-option=?'])
            self.assertEqual(call.exception.args, (0,))
        expected = """
        Each format may support a different set of options
        2013.com.canonical.plainbox::hexr: 
        2013.com.canonical.plainbox::html: 
        2013.com.canonical.plainbox::json: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments, with-job-via, with-job-hash, with-category-map, with-certification-status, machine-json
        2013.com.canonical.plainbox::rfc822: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments, with-job-via, with-job-hash, with-category-map, with-certification-status
        2013.com.canonical.plainbox::text: with-io-log, squash-io-log, flatten-io-log, with-run-list, with-job-list, with-resource-map, with-job-defs, with-attachments, with-comments, with-job-via, with-job-hash, with-category-map, with-certification-status
        2013.com.canonical.plainbox::xlsx: with-sys-info, with-summary, with-job-description, with-text-attachments, with-unit-categories
        """
        self.assertIn(cleandoc(expected) + "\n", io.combined)

    def tearDown(self):
        shutil.rmtree(self._sandbox)
        os.environ = self._env
        warnings.resetwarnings()
