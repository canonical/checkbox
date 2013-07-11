
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
:mod:`plainbox.impl.provider` -- PlainBox providers
===================================================

Providers are a mechanism by which PlainBox can enumerate jobs and whitelists.
Currently there are only v1 (as in version one) providers that basically have
to behave as CheckBox itself (mini CheckBox forks for example)

There is ongoing work and discussion on V2 providers that would have a
lower-level interface and would be able to define new job types, new whitelist
types and generally all the next-gen semantics.

PlainBox does not come with any real provider by default. PlainBox sometimes
creates special dummy providers that have particular data in them for testing.


V1 providers
------------

The first (current) version of PlainBox providers has the following properties,
this is also described by :class:`IProvider1`::

    * there is a directory with '.txt' or '.txt.in' files with RFC822-encoded
      job definitions. The definitions need a particular set of keys to work.

    * there is a directory with '.whitelist' files that contain a list (one per
      line) of job definitions to execute.

    * there is a directory with additional executables (added to PATH)

    * there is a directory with an additional python3 libraries (added to
      PYTHONPATH)
"""

import abc
import logging


logger = logging.getLogger("plainbox.provider")


class ProviderNotFound(LookupError):
    """
    Exception used to report that a provider cannot be located
    """


class IProviderBackend1(metaclass=abc.ABCMeta):
    """
    Provider for the current type of tests.

    This class provides the APIs required by the internal implementation
    that are not considered normal public APIs. The only consumer of the
    those methods and properties are internal to plainbox.
    """

    @abc.abstractproperty
    def CHECKBOX_SHARE(self):
        """
        Return the required value of CHECKBOX_SHARE environment variable.

        .. note::
            This variable is only required by one script.
            It would be nice to remove this later on.
        """

    @abc.abstractproperty
    def extra_PYTHONPATH(self):
        """
        Return additional entry for PYTHONPATH, if needed.

        This entry is required for CheckBox scripts to import the correct
        CheckBox python libraries.

        .. note::
            The result may be None
        """

    @abc.abstractproperty
    def extra_PATH(self):
        """
        Return additional entry for PATH

        This entry is required to lookup CheckBox scripts.
        """


class IProvider1(metaclass=abc.ABCMeta):
    """
    Provider for the current type of tests

    Also known as the 'checkbox-like' provider.
    """

    @abc.abstractproperty
    def name(self):
        """
        name of this provider

        This name should be dbus-friendly. It should not be localizable.
        """

    @abc.abstractproperty
    def CHECKBOX_SHARE(self):
        """
        Return the required value of CHECKBOX_SHARE environment variable.

        .. note::
            This variable is only required by one script.
            It would be nice to remove this later on.
        """

    @abc.abstractproperty
    def extra_PYTHONPATH(self):
        """
        Return additional entry for PYTHONPATH, if needed.

        This entry is required for CheckBox scripts to import the correct
        CheckBox python libraries.

        .. note::
            The result may be None
        """

    @abc.abstractproperty
    def extra_PATH(self):
        """
        Return additional entry for PATH

        This entry is required to lookup CheckBox scripts.
        """

    @abc.abstractmethod
    def get_builtin_whitelists(self):
        """
        Load all the built-in whitelists and return them
        """

    @abc.abstractmethod
    def get_builtin_jobs(self):
        """
        Load all the built-in jobs and return them
        """


class DummyProvider1(IProvider1):
    """
    Dummy provider useful for creating isolated test cases
    """

    def __init__(self, job_list=None, whitelist_list=None, **extras):
        self._job_list = job_list or []
        self._whitelist_list = whitelist_list or []
        self._extras = extras
        self._patch_provider_field()

    def _patch_provider_field(self):
        # NOTE: each v1 job needs a _checkbox attribute that points to the
        # provider. Since many tests use make_job() which does not set it for
        # obvious reasons it needs to be patched-in.
        for job in self._job_list:
            if job._checkbox is None:
                job._checkbox = self

    @property
    def name(self):
        return self._extras.get('name', "dummy")

    @property
    def CHECKBOX_SHARE(self):
        return self._extras.get('CHECKBOX_SHARE', "")

    @property
    def extra_PYTHONPATH(self):
        return self._extras.get("PYTHONPATH")

    @property
    def extra_PATH(self):
        return self._extras.get("PATH", "")

    def get_builtin_whitelists(self):
        return self._whitelist_list

    def get_builtin_jobs(self):
        return self._job_list
