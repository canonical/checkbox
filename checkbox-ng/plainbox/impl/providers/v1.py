# This file is part of Checkbox.
#
# Copyright 2013-2015 Canonical Ltd.
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
:mod:`plainbox.impl.providers.v1` -- Implementation of V1 provider
==================================================================

Most of the implementation is available in
:mod:`plainbox.impl.secure.providers.v1`
"""

__all__ = ['Provider1', 'InsecureProvider1PlugInCollection', 'all_providers',
           'get_insecure_PROVIDERPATH_list', ]

import logging
import os

from plainbox.impl.secure.plugins import FsPlugInCollection
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.providers.v1 import Provider1PlugIn
from plainbox.impl.secure.providers.v1 import get_secure_PROVIDERPATH_list


logger = logging.getLogger("plainbox.providers.v1")


def get_user_PROVIDERPATH_entry():
    """
    Computes the per-user component of PROVIDERPATH

    :returns:
        `$XDG_DATA_HOME/plainbox-providers-1`
    """
    XDG_DATA_HOME = os.getenv(
        'XDG_DATA_HOME', os.path.expanduser("~/.local/share/"))
    return os.path.join(XDG_DATA_HOME, "plainbox-providers-1")


def get_insecure_PROVIDERPATH_list():
    """
    Computes the insecure value of PROVIDERPATH.

    This value is *not* used by `plainbox-trusted-launcher-1` executable since
    it would involve reading files outside of the control by the local
    administrator. This value is used for handing non-root jobs.

    :returns:
        A list of three strings:
        * `/usr/local/share/plainbox-providers-1`
        * `/usr/share/plainbox-providers-1`
        * `$XDG_DATA_HOME/plainbox-providers-1`
    """
    return get_secure_PROVIDERPATH_list() + [get_user_PROVIDERPATH_entry()]


class InsecureProvider1PlugInCollection(FsPlugInCollection):
    """
    A collection of v1 provider plugins.

    This FsPlugInCollection subclass carries proper, built-in defaults, that
    make loading providers easier.

    This particular class loads providers from both the system-wide managed
    locations and per-user location. In addition the list of locations searched
    can be changed by setting the ``PROVIDERPATH``, which behaves just like
    PATH, but is used for looking up providers.
    """

    def __init__(self, **kwargs):
        PROVIDERPATH = os.getenv("PROVIDERPATH")
        if PROVIDERPATH is None:
            dir_list = get_insecure_PROVIDERPATH_list()
        else:
            dir_list = PROVIDERPATH.split(os.path.pathsep)
        super().__init__(
            dir_list, '.provider', wrapper=Provider1PlugIn, **kwargs)


# Collection of all providers
all_providers = InsecureProvider1PlugInCollection()
