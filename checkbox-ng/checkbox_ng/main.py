# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`checkbox_ng.main` -- command line interface
=================================================
"""

import logging
import sys

from plainbox.impl.commands import PlainBoxToolBase
from plainbox.impl.commands.check_config import CheckConfigCommand
from plainbox.impl.commands.dev import DevCommand
from plainbox.impl.commands.script import ScriptCommand

from checkbox_ng import __version__ as version
from checkbox_ng.commands.certification import CertificationCommand
from checkbox_ng.commands.cli import CliCommand
from checkbox_ng.commands.sru import SRUCommand
try:
    from checkbox_ng.commands.service import ServiceCommand
except ImportError:
    pass
from checkbox_ng.config import CertificationConfig, CheckBoxConfig, CDTSConfig


logger = logging.getLogger("checkbox.ng.main")

checkbox_cli_settings = {
    'subparser_name': 'checkbox-cli',
    'subparser_help': 'application for system testing',
    'default_whitelist': 'default',
    'default_providers': ['2013.com.canonical.certification:checkbox'],
    'welcome_text': """\
Welcome to System Testing!
Checkbox provides tests to confirm that your system is working properly. \
Once you are finished running the tests, you can view a summary report for \
your system.
Warning: Some tests could cause your system to freeze or become \
unresponsive. Please save all your work and close all other running \
applications before beginning the testing process."""
}

cdts_cli_settings = {
    'subparser_name': 'driver-test-suite-cli',
    'subparser_help': 'driver test suite application',
    'default_whitelist': 'ihv-firmware',
    'default_providers': ['2013.com.canonical:canonical-driver-test-suite'],
    'welcome_text': """\
Welcome to the Canonical Driver Test Suite.
This program contains automated and manual tests to help you discover issues \
that will arise when running your device drivers on Ubuntu.
This application will step the user through these tests in a predetermined \
order and automatically collect both system information as well as test \
results. It will also prompt the user for input when manual testing is \
required.
The run time for the tests is determined by which tests you decide to \
execute. The user will have the opportunity to customize the test run to \
accommodate the driver and the amount of time available for testing.
If you have any questions during or after completing your test run, please \
do not hesitate to contact your Canonical account representative.
To begin, simply press the Continue button below and follow the onscreen \
instructions."""
}

cert_cli_settings = {
    'subparser_name': 'certification-server',
    'subparser_help': 'application for server certification',
    'default_whitelist': 'server-selftest-14.04',
    'default_providers': ['2013.com.canonical.certification:certification-server'],
    'welcome_text': """\
Welcome to System Certification!
This application will gather information from your system. Then you will be \
asked manual tests to confirm that the system is working properly. Finally, \
you will be asked for the Secure ID of the computer to submit the \
information to the certification.canonical.com database.
To learn how to create or locate the Secure ID, please see here:
https://certification.canonical.com/"""
}


class CheckBoxNGTool(PlainBoxToolBase):

    @classmethod
    def get_exec_name(cls):
        return "checkbox"

    @classmethod
    def get_exec_version(cls):
        return "{}.{}.{}".format(*version[:3])

    @classmethod
    def get_config_cls(cls):
        return CheckBoxConfig

    def add_subcommands(self, subparsers):
        SRUCommand(
            self._provider_list, self._config).register_parser(subparsers)
        CheckConfigCommand(
            self._config).register_parser(subparsers)
        ScriptCommand(
            self._provider_list, self._config).register_parser(subparsers)
        DevCommand(
            self._provider_list, self._config).register_parser(subparsers)
        CliCommand(
            self._provider_list, self._config, checkbox_cli_settings
            ).register_parser(subparsers)
        CliCommand(
            self._provider_list, self._config, cdts_cli_settings
            ).register_parser(subparsers)
        CertificationCommand(
            self._provider_list, self._config, cert_cli_settings
            ).register_parser(subparsers)
        try:
            ServiceCommand(self._provider_list, self._config).register_parser(
                subparsers)
        except NameError:
            pass


class CertificationNGTool(CheckBoxNGTool):

    @classmethod
    def get_config_cls(cls):
        return CertificationConfig


class CDTSTool(CheckBoxNGTool):

    @classmethod
    def get_config_cls(cls):
        return CDTSConfig


def main(argv=None):
    """
    checkbox command line utility
    """
    raise SystemExit(CheckBoxNGTool().main(argv))


def checkbox_cli(argv=None):
    """
    CheckBox command line utility
    """
    if argv:
        args = argv
    else:
        args = sys.argv[1:]
    raise SystemExit(
        CheckBoxNGTool().main(['checkbox-cli'] + args))


def cdts_cli(argv=None):
    """
    certification-server command line utility
    """
    if argv:
        args = argv
    else:
        args = sys.argv[1:]
    raise SystemExit(
        CDTSTool().main(['driver-test-suite-cli'] + args))


def cert_server(argv=None):
    """
    certification-server command line utility
    """
    if argv:
        args = argv
    else:
        args = sys.argv[1:]
    raise SystemExit(
        CertificationNGTool().main(['certification-server'] + args))
