# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.commands.dev` -- dev sub-command
====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from logging import getLogger

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.cmd_analyze import AnalyzeCommand
from plainbox.impl.commands.crash import CrashCommand
from plainbox.impl.commands.cmd_list import ListCommand
from plainbox.impl.commands.logtest import LogTestCommand
from plainbox.impl.commands.cmd_parse import ParseCommand
from plainbox.impl.commands.cmd_script import ScriptCommand
from plainbox.impl.commands.cmd_special import SpecialCommand


logger = getLogger("plainbox.commands.dev")


class DevCommand(PlainBoxCommand):
    """
    Command hub for various development commands.
    """

    def __init__(self, provider_loader, config_loader):
        self.provider_loader = provider_loader
        self.config_loader = config_loader

    def invoked(self, ns):
        raise NotImplementedError()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "dev", help=_("development commands"),
            prog="plainbox dev",
            usage=_("plainbox dev <subcommand> ..."))
        subdev = parser.add_subparsers()
        ScriptCommand(self.provider_loader,
                      self.config_loader).register_parser(subdev)
        SpecialCommand(self.provider_loader,
                       self.config_loader).register_parser(subdev)
        AnalyzeCommand(self.provider_loader,
                       self.config_loader).register_parser(subdev)
        ParseCommand().register_parser(subdev)
        CrashCommand().register_parser(subdev)
        LogTestCommand().register_parser(subdev)
        ListCommand(self.provider_loader).register_parser(subdev)
