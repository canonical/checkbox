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
:mod:`plainbox.impl.commands` -- shared code for plainbox sub-commands
======================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
import abc
import logging

from plainbox.impl.clitools import CommandBase
from plainbox.impl.clitools import ToolBase
from plainbox.public import get_providers


logger = logging.getLogger("plainbox.commands")


class PlainBoxToolBase(ToolBase):
    """
    Base class for implementing commands like 'plainbox'.

    The tools support a variety of sub-commands, logging and debugging
    support. If argcomplete module is available and used properly in
    the shell then advanced tab-completion is also available.

    There are four methods to implement for a basic tool. Those are:

    1. :meth:`get_exec_name()` -- to know how the command will be called
    2. :meth:`get_exec_version()` -- to know how the version of the tool
    3. :meth:`add_subcommands()` -- to add some actual commands to execute
    4. :meth:`get_config_cls()` -- to know which config to use

    This class has some complex control flow to support important and
    interesting use cases. There are some concerns to people that subclass this
    in order to implement their own command line tools.

    The first concern is that input is parsed with two parsers, the early
    parser and the full parser. The early parser quickly checks for a fraction
    of supported arguments and uses that data to initialize environment before
    construction of a full parser is possible. The full parser sees the
    reminder of the input and does not re-parse things that where already
    handled.

    The second concern is that this command natively supports the concept of a
    config object and a provider object. This may not be desired by all users
    but it is the current state as of this writing. This means that by the time
    eary init is done we have a known provider and config objects that can be
    used to instantiate command objects in :meth:`add_subcommands()`. This API
    might change when full multi-provider is available but details are not
    known yet.
    """

    @classmethod
    @abc.abstractmethod
    def get_config_cls(cls):
        """
        Get the Config class that is used by this implementation.

        This can be overridden by subclasses to use a different config class
        that is suitable for the particular application.
        """

    def _load_config(self):
        return self.get_config_cls().get()

    def _load_providers(self):
        logger.info("Loading all providers...")
        return get_providers()


class PlainBoxCommand(CommandBase):
    """
    Simple interface class for plainbox commands.

    Command objects like this are consumed by PlainBoxTool subclasses to
    implement hierarchical command system. The API supports arbitrary many sub
    commands in arbitrary nesting arrangement.
    """

    gettext_domain = "plainbox"
