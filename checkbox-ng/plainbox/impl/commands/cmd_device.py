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
:mod:`plainbox.impl.commands.cmd_device` -- device sub-command (command)
========================================================================

This module contains the user interface parts of the 'plainbox device' command.
"""
from logging import getLogger

from plainbox.i18n import docstring
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.commands import PlainBoxCommand


logger = getLogger("plainbox.commands.device")


@docstring(
    N_("""
    device management commands

    This command can be used to show the device that plainbox is executing

    @EPILOG@

    TBD
    """))
class DeviceCommand(PlainBoxCommand):

    def invoked(self, ns):
        from plainbox.impl.commands.inv_device import DeviceInvocation
        return DeviceInvocation(ns).run()

    def register_parser(self, subparsers):
        parser = self.add_subcommand(subparsers)
        parser.prog = 'plainbox device'