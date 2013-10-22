# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.providers.v1` -- Implementation of V1 provider
==================================================================

Most of the implementation is available in
:mod:`plainbox.impl.secure.providers.v1`
"""

__all__ = ['DummyProvider1', 'Provider1', 'Provider1PlugInCollection',
           'all_providers', 'get_default_PROVIDERPATH', ]

import logging
import os

from plainbox.abc import IProvider1, IProviderBackend1
from plainbox.impl.secure.providers.v1 import Provider1PlugInCollection
from plainbox.impl.secure.providers.v1 import Provider1


logger = logging.getLogger("plainbox.providers.v1")


class DummyProvider1(IProvider1, IProviderBackend1):
    """
    Dummy provider useful for creating isolated test cases
    """

    def __init__(self, job_list=None, whitelist_list=None, **extras):
        self._job_list = job_list or []
        self._whitelist_list = whitelist_list or []
        self._extras = extras
        self._patch_provider_field()

    def _patch_provider_field(self):
        # NOTE: each v1 job needs a _provider attribute that points to the
        # provider. Since many tests use make_job() which does not set it for
        # obvious reasons it needs to be patched-in.
        for job in self._job_list:
            if job._provider is None:
                job._provider = self

    @property
    def name(self):
        return self._extras.get('name', "dummy")

    @property
    def description(self):
        return self._extras.get(
            'description', "A dummy provider useful for testing")

    @property
    def CHECKBOX_SHARE(self):
        return self._extras.get('CHECKBOX_SHARE', "")

    @property
    def extra_PYTHONPATH(self):
        return self._extras.get("PYTHONPATH")

    @property
    def extra_PATH(self):
        return self._extras.get("PATH", "")

    @property
    def uses_policykit(self):
        return bool(self._extras.get("uses_policykit", ""))

    def get_builtin_whitelists(self):
        return self._whitelist_list

    def get_builtin_jobs(self):
        return self._job_list


def get_default_PROVIDERPATH():
    """
    Computes the default value for PROVIDERPATH.

    PROVIDERPATH should contain two directory entries:

        * /usr/share/plainbox-providers-1
        * $XDG_DATA_HOME/plainbox-providers-1
    """
    sys_wide = "/usr/share/plainbox-providers-1"
    per_user = os.path.join(
        os.getenv('XDG_DATA_HOME', os.path.expanduser("~/.local/share/")),
        "plainbox-providers-1")
    return os.path.pathsep.join([sys_wide, per_user])


class Provider1PlugInCollection(Provider1PlugInCollection):
    """
    A collection of v1 provider plugins.

    This class is just like FsPlugInCollection but knows the proper arguments
    (PROVIDERPATH and the extension)
    """

    DEFAULT_PROVIDERPATH = get_default_PROVIDERPATH()


# Collection of all providers
all_providers = Provider1PlugInCollection()
