# This file is part of Checkbox.
#
# Copyright 2013-2020 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
APIs for working with providers.

:mod:`plainbox.impl.providers` -- providers package
===================================================

Providers are a mechanism by which PlainBox can enumerate jobs and test plans.
Currently there are only v1 (as in version one) providers that basically have
to behave as CheckBox itself (mini CheckBox forks for example)

V1 providers
------------

The first (current) version of PlainBox providers has the following properties,
this is also described by :class:`IProvider1`::

    * there is a directory with '.txt' or '.txt.in' files with RFC822-encoded
      job definitions. The definitions need a particular set of keys to work.

    * there is a directory with additional executables (added to PATH)

    * there is a directory with an additional python3 libraries (added to
      PYTHONPATH)
"""

import logging
import os

from plainbox.impl.providers.embedded_providers import (
    EmbeddedProvider1PlugInCollection)

logger = logging.getLogger("plainbox.providers.__init__")


class ProviderNotFound(LookupError):

    """ Exception used to report that a provider cannot be located. """


def get_providers(*, only_secure: bool=False) -> 'List[Provider1]':
    """
    Find and load all providers that are available.

    :param only_secure:
        (keyword only) Return only providers that are deemed secure.
    :returns:
        A list of Provider1 objects, created in no particular order.

    This function can be used to get a list of all available providers. Most
    applications will just want the default, regular list of providers, without
    bothering to restrict themselves to the secure subset.

    Those are the providers that can run jobs as root using the
    ``plainbox-trusted-launcher-1`` mechanism. Depending on the *policykit*
    Policy, those might start without prompting the user for the password. If
    you want to load only them, use the `only_secure` option.
    """
    from plainbox.impl.providers import special
    if only_secure:
        from plainbox.impl.secure.providers.v1 import all_providers
    else:
        from plainbox.impl.providers.v1 import all_providers
    all_providers.load()
    std_providers= [
        special.get_manifest(),
        special.get_exporters(),
        special.get_categories(),
    ] + all_providers.get_all_plugin_objects()
    if only_secure:
        return std_providers

    def qualified_name(provider):
        return "{}:{}".format(provider.namespace, provider.name)
    sideload_path = os.path.expandvars(os.path.join(
        '/var', 'tmp', 'checkbox-providers'))
    embedded_providers = EmbeddedProvider1PlugInCollection(sideload_path)
    loaded_provs = embedded_providers.get_all_plugin_objects()
    for p in loaded_provs:
        logger.warning("Using sideloaded provider: %s from %s", p, p.base_dir)
    sl_qual_names = [qualified_name(p) for p in loaded_provs]
    for std_prov in std_providers:
        if qualified_name(std_prov) in sl_qual_names:
            # this provider got overriden by sideloading
            # so let's not load the original one
            continue
        loaded_provs.append(std_prov)
    if not loaded_provs:
        message = '\n'.join(( _("No providers found! Paths searched:"),
            *all_providers.provider_search_paths))
        raise SystemExit(message)
    return loaded_provs
