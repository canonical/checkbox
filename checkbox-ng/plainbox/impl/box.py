# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.box` -- command line interface
==================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging

from plainbox import __version__ as version
from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.commands import PlainBoxToolBase
from plainbox.impl.commands.check_config import CheckConfigCommand
from plainbox.impl.commands.dev import DevCommand
from plainbox.impl.commands.run import RunCommand
from plainbox.impl.commands.selftest import SelfTestCommand
from plainbox.impl.commands.service import ServiceCommand
from plainbox.impl.commands.sru import SRUCommand
from plainbox.impl.logging import setup_logging


logger = logging.getLogger("plainbox.box")


class PlainBoxTool(PlainBoxToolBase):
    """
    Command line interface to PlainBox
    """

    @classmethod
    def get_config_cls(cls):
        """
        Get the Config class that is used by this implementation.

        This can be overriden by subclasses to use a different config class
        that is suitable for the particular application.
        """
        return PlainBoxConfig

    @classmethod
    def get_exec_name(cls):
        """
        Get the name of this executable
        """
        return "plainbox"

    @classmethod
    def get_exec_version(cls):
        """
        Get the version reported by this executable
        """
        return "{}.{}.{}".format(*version[:3])

    def add_subcommands(self, subparsers):
        """
        Add top-level subcommands to the argument parser.

        This can be overriden by subclasses to use a different set of
        top-level subcommands.
        """
        # TODO: switch to plainbox plugins
        RunCommand(self._provider_list, self._config).register_parser(subparsers)
        SelfTestCommand().register_parser(subparsers)
        SRUCommand(self._provider_list, self._config).register_parser(subparsers)
        CheckConfigCommand(self._config).register_parser(subparsers)
        DevCommand(self._provider_list, self._config).register_parser(subparsers)
        ServiceCommand(self._provider_list, self._config).register_parser(
            subparsers)


def main(argv=None):
    raise SystemExit(PlainBoxTool().main(argv))


# Setup logging before anything else starts working.
# If we do it in main() or some other place then unit tests will see
# "leaked" log files which are really closed when the runtime shuts
# down but not when the tests are finishing
setup_logging()
