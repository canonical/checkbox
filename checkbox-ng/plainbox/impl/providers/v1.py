# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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

__all__ = ['DummyProvider1', 'Provider1', 'InsecureProvider1PlugInCollection',
           'all_providers', 'get_insecure_PROVIDERPATH_list', ]

import logging
import os

from plainbox.abc import IProvider1, IProviderBackend1
from plainbox.impl.secure.plugins import FsPlugInCollection
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.providers.v1 import Provider1PlugIn
from plainbox.impl.secure.providers.v1 import get_secure_PROVIDERPATH_list


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
    def version(self):
        return self._extras.get('version', '1.0')

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
    def bin_dir(self):
        return self._extras.get("bin_dir")

    @property
    def jobs_dir(self):
        return self._extras.get("jobs_dir")

    @property
    def whitelists_dir(self):
        return self._extras.get("whitelists_dir")

    def secure(self):
        return False

    def get_builtin_whitelists(self):
        return self._whitelist_list

    def get_builtin_jobs(self):
        return self._job_list

    def load_all_jobs(self):
        return self._job_list, []

    def get_all_executables(self):
        return self._extras.get("get_all_executables", [])


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

    def __init__(self):
        PROVIDERPATH = os.getenv("PROVIDERPATH")
        if PROVIDERPATH is None:
            dir_list = get_insecure_PROVIDERPATH_list()
        else:
            dir_list = PROVIDERPATH.split(os.path.pathsep)
        super().__init__(dir_list, '.provider', wrapper=Provider1PlugIn)


# Collection of all providers
all_providers = InsecureProvider1PlugInCollection()
