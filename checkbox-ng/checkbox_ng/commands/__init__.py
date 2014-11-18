# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
:mod:`checkbox_ng.commands` -- shared code for checkbox-ng sub-commands
=======================================================================
"""

from plainbox.impl.clitools import CommandBase


class CheckboxCommand(CommandBase):
    """
    Simple interface class for checkbox-ng commands.

    Command objects like this are consumed by CheckBoxNGTool subclasses to
    implement hierarchical command system. The API supports arbitrary many sub
    commands in arbitrary nesting arrangement.
    """

    gettext_domain = "checkbox-ng"

    def __init__(self, provider_loader, config_loader):
        """
        Initialize a command with the specified arguments.

        :param provider_loader:
            A callable returning a list of Provider1 objects
        :param config_loader:
            A callable returning a Config object
        """
        self._provider_loader = provider_loader
        self._config_loader = config_loader

    @property
    def provider_loader(self):
        """
        a callable returning a list of PlainBox providers associated with this
        command
        """
        return self._provider_loader

    @property
    def config_loader(self):
        """
        a callable returning a Config object
        """
        return self._config_loader
