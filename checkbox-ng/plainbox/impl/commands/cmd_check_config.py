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
:mod:`plainbox.impl.commands.cmd_check_config` -- check-config sub-command
==========================================================================
"""
from plainbox.impl.commands import PlainBoxCommand
from plainbox.i18n import gettext as _


class CheckConfigCommand(PlainBoxCommand):
    """
    Command for checking and displaying plainbox configuration
    """

    def __init__(self, config):
        self.config = config

    def invoked(self, ns):
        from plainbox.impl.commands.inv_check_config \
            import CheckConfigInvocation
        return CheckConfigInvocation(self.config).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "check-config",
            help=_("check and display plainbox configuration"),
            prog="plainbox check-config")
        parser.set_defaults(command=self)
