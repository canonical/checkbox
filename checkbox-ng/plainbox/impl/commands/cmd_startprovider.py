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
:mod:`plainbox.impl.commands.cmd_startprovider` -- startprovider sub-command
============================================================================
"""
from plainbox.i18n import docstring
from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.secure.providers.v1 import IQNValidator


class IQN(str):
    """
    A string subclass that validates values with the IQNValidator
    """

    _validator = IQNValidator()

    def __new__(mcls, value):
        problem = mcls._validator(None, value)
        if problem:
            raise ValueError(problem)
        return super().__new__(mcls, value)


@docstring(
    # TRANSLATORS: please leave various options (both long and short forms),
    # environment variables and paths in their original form. Also keep the
    # special @EPILOG@ string. The first line of the translation is special and
    # is used as the help message. Please keep the pseudo-statement form and
    # don't finish the sentence with a dot. Pay extra attention to whitespace.
    # It must be correctly preserved or the result won't work. In particular
    # the leading whitespace *must* be preserved and *must* have the same
    # length on each line.
    N_("""
    create a new provider (directory)

    Creates a new provider from a built-in skeleton.

    @EPILOG@

    The name of the provider must follow the pattern ``YYYY.example.org:name``
    where ``YYYY`` is a four-digit year when the author of the provider owned
    the domain (here, ``example.org``) and ``name`` is arbitrary identifier
    that is managed by the owner of that domain. The identifier should be
    constrained to ASCII, digits and the dash character.

    This naming scheme allows anyone that ever owned a domain name to come up
    with non-clashing provider identifiers. Those identifiers are going to be
    used in fully qualified names of various objects.

    This command creates a new skeleton test provider for PlainBox. The
    generated content should be edited to fit a particular purpose.
    """))
class StartProviderCommand(PlainBoxCommand):

    def invoked(self, ns):
        from plainbox.impl.commands.inv_startprovider \
            import StartProviderInvocation
        return StartProviderInvocation(ns.name).run()

    def register_parser(self, subparsers):
        parser = self.add_subcommand(subparsers)
        parser.prog = 'plainbox startprovider'
        parser.add_argument(
            'name',
            metavar=_("name"),
            type=IQN,
            # TRANSLATORS: please keep the YYYY.example... text unchanged or at
            # the very least translate only YYYY and some-name. In either case
            # some-name must be a reasonably-ASCII string (should be safe for a
            # portable directory name)
            help=_("provider name, eg: YYYY.example.org:some-name"))
        parser.set_defaults(command=self)
