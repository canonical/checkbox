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
checkbox_ng.test_main
=====================

Test definitions for checkbox_ng.main module
"""

from inspect import cleandoc
from unittest import TestCase

from plainbox.testing_utils.io import TestIO

from checkbox_ng import __version__ as version
from checkbox_ng.main import cert_server, main


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
        usage: checkbox [-h] [--version] [--providers {all,src,stub}] [-v] [-D] [-C]
                        [-T LOGGER] [-P] [-I]
                        
                        {sru,check-config,script,dev,checkbox-cli,driver-test-suite-cli,certification-server,service}
                        ...

        positional arguments:
          {sru,check-config,script,dev,checkbox-cli,driver-test-suite-cli,certification-server,service}
            sru                 run automated stable release update tests
            check-config        check and display plainbox configuration
            script              run a command from a job
            dev                 development commands
            checkbox-cli        application for system testing
            driver-test-suite-cli
                                driver test suite application
            certification-server
                                application for server certification
            service             spawn dbus service

        optional arguments:
          -h, --help            show this help message and exit
          --version             show program's version number and exit

        provider list and development:
          --providers {all,src,stub}
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
        usage: checkbox [-h] [--version] [--providers {all,src,stub}] [-v] [-D] [-C]
                        [-T LOGGER] [-P] [-I]
                        
                        {sru,check-config,script,dev,checkbox-cli,driver-test-suite-cli,certification-server,service}
                        ...
        checkbox: error: too few arguments

        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")


class TestCertServer(TestCase):

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                cert_server(['--help'])
        self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: checkbox certification-server [-h] [--check-config] [--not-interactive]
                                             [--secure-id SECURE-ID]
                                             [--destination URL] [--staging]
                                             [-i PATTERN] [-x PATTERN] [-w WHITELIST]

        optional arguments:
          -h, --help            show this help message and exit
          --check-config        Run check-config
          --not-interactive     Skip tests that require interactivity

        certification-specific options:
          --secure-id SECURE-ID
                                Associate submission with a machine using this SECURE-
                                ID (None)
          --destination URL     POST the test report XML to this URL (https://certific
                                ation.canonical.com/submissions/submit/)
          --staging             Override --destination to use the staging
                                certification website

        job definition options:
          -i PATTERN, --include-pattern PATTERN
                                include jobs matching the given regular expression
          -x PATTERN, --exclude-pattern PATTERN
                                exclude jobs matching the given regular expression
          -w WHITELIST, --whitelist WHITELIST
                                load whitelist containing run patterns
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")
