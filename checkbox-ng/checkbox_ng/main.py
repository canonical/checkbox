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
import os
import sys

from plainbox.impl.commands import PlainBoxToolBase
from plainbox.impl.commands.check_config import CheckConfigCommand
from plainbox.impl.commands.dev import DevCommand
from plainbox.impl.commands.script import ScriptCommand
from plainbox.impl.logging import setup_logging

from checkbox_ng import __version__ as version
from checkbox_ng.commands.certification import CertificationCommand
from checkbox_ng.commands.cli import CliCommand
from checkbox_ng.commands.sru import SRUCommand
from checkbox_ng.commands.submit import SubmitCommand

try:
    from checkbox_ng.commands.service import ServiceCommand
    dbus_supported = True
except ImportError:
    dbus_supported = False
from checkbox_ng.config import CertificationConfig, CheckBoxConfig, CDTSConfig


logger = logging.getLogger("checkbox.ng.main")


class CheckBoxNGTool(PlainBoxToolBase):

    @classmethod
    def get_exec_name(cls):
        return "checkbox"

    @classmethod
    def get_exec_version(cls):
        return cls.format_version_tuple(version)

    @classmethod
    def get_config_cls(cls):
        return CheckBoxConfig

    def get_gettext_domain(self):
        return "checkbox-ng"

    def get_locale_dir(self):
        return os.getenv("CHECKBOX_NG_LOCALE_DIR", None)

    def add_subcommands(self, subparsers):
        SRUCommand(
            self._provider_list, self._config).register_parser(subparsers)
        CheckConfigCommand(
            self._config).register_parser(subparsers)
        SubmitCommand(
            self._config).register_parser(subparsers)
        ScriptCommand(
            self._provider_list, self._config).register_parser(subparsers)
        DevCommand(
            self._provider_list, self._config).register_parser(subparsers)
        if dbus_supported:
            ServiceCommand(self._provider_list, self._config).register_parser(
                subparsers)


def main(argv=None):
    """
    checkbox command line utility
    """
    raise SystemExit(CheckBoxNGTool().main(argv))

setup_logging()
