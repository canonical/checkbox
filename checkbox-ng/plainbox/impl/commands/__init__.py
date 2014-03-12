# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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

from plainbox.i18n import gettext as _
from plainbox.impl.clitools import CommandBase, ToolBase
from plainbox.impl.providers.special import CheckBoxSrcProvider
from plainbox.impl.providers.special import get_stubbox_def
from plainbox.impl.providers.v1 import all_providers
from plainbox.impl.secure.providers.v1 import Provider1


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

    def __init__(self):
        """
        Initialize all the variables, real stuff happens in main()
        """
        super().__init__()
        self._config = None  # set in late_init()
        self._provider_list = []  # updated in late_init()

    @classmethod
    @abc.abstractmethod
    def get_config_cls(cls):
        """
        Get the Config class that is used by this implementation.

        This can be overridden by subclasses to use a different config class
        that is suitable for the particular application.
        """

    def late_init(self, early_ns):
        """
        Overridden version of late_init().

        This method loads the configuration object and the list of providers
        and stores them as instance attributes.
        """
        super().late_init(early_ns)
        # Load plainbox configuration
        self._config = self.get_config_cls().get()
        # XXX: we cannot change _provider_list as the particular list object is
        # already passed as argument to several command classes. It seems safe
        # to append items to it though.
        self._provider_list.extend(self.get_provider_list(early_ns))

    def get_provider_list(self, ns):
        """
        Get the list of job providers.

        This method looks at --providers argument to figure out which
        providers to expose to all of the commands.
        """
        # If the default value of 'None' was set for the checkbox (provider)
        # argument then load the actual provider name from the configuration
        # object (default for that is 'auto').
        if ns.providers is None:
            ns.providers = self._config.default_provider
        assert ns.providers in ('all', 'src', 'stub')
        # Decide which providers to expose to the rest of plainbox
        if ns.providers == 'all':
            return self._load_really_all_providers()
        elif ns.providers == 'src':
            return self._load_checkbox_source_provider()
        elif ns.providers == 'stub':
            return self._load_stub_provider_only()

    def _load_really_all_providers(self):
        provider_list = []
        # StubBox is always enabled
        provider_list.append(
            Provider1.from_definition(get_stubbox_def(), secure=False))
        # Load checkbox-src if working from source
        try:
            provider_list.append(CheckBoxSrcProvider())
        except LookupError:
            pass
        # Load all normal providers
        all_providers.load()
        provider_list.extend(all_providers.get_all_plugin_objects())
        return provider_list

    def _load_checkbox_source_provider(self):
        return [CheckBoxSrcProvider()]

    def _load_stub_provider_only(self):
        return [Provider1.from_definition(get_stubbox_def(), secure=False)]

    def add_early_parser_arguments(self, parser):
        """
        Overridden version of add_early_parser_arguments().

        This method adds the -c|--checkbox argument to the set of early parser
        arguments, so that it is visible in autocomplete and help.
        """
        group = parser.add_argument_group(title=_("provider list and development"))
        group.add_argument(
            '--providers',
            action='store',
            choices=['all', 'src', 'stub'],
            # None is a special value that means 'use whatever is configured'
            default=None,
            help=_("which providers to load"))
        super().add_early_parser_arguments(parser)


class PlainBoxCommand(CommandBase):
    """
    Simple interface class for plainbox commands.

    Command objects like this are consumed by PlainBoxTool subclasses to
    implement hierarchical command system. The API supports arbitrary many sub
    commands in arbitrary nesting arrangement.
    """

    gettext_domain = "plainbox"
