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
:mod:`checkbox_ng.main` -- command line interface
=================================================
"""

import logging

from plainbox.impl.commands.check_config import CheckConfigCommand
from plainbox.impl.commands.sru import SRUCommand
from plainbox.impl.commands.script import ScriptCommand
from plainbox.impl.commands.dev import DevCommand
from plainbox.impl.box import PlainBox

from checkbox_ng import __version__ as version
from checkbox_ng.config import CheckBoxConfig


logger = logging.getLogger("checkbox.ng.main")


class CheckBoxNG(PlainBox):

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
        SRUCommand(self._provider, self._config).register_parser(subparsers)
        CheckConfigCommand(self._config).register_parser(subparsers)
        ScriptCommand(self._provider, self._config).register_parser(subparsers)
        DevCommand(self._provider, self._config).register_parser(subparsers)


def main(argv=None):
    """
    checkbox command line utility
    """
    raise SystemExit(CheckBoxNG().main(argv))
