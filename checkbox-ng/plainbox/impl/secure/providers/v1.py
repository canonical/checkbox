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
:mod:`plainbox.impl.secure.providers.v1` -- Implementation of V1 provider
=========================================================================
"""

import errno
import io
import logging
import os

from plainbox.abc import IProvider1, IProviderBackend1
from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.config import Config, Variable
from plainbox.impl.secure.config import IValidator
from plainbox.impl.secure.config import NotEmptyValidator
from plainbox.impl.secure.config import PatternValidator
from plainbox.impl.secure.plugins import FsPlugInCollection
from plainbox.impl.secure.plugins import IPlugIn
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.rfc822 import load_rfc822_records


logger = logging.getLogger("plainbox.secure.providers.v1")


class Provider1(IProvider1, IProviderBackend1):
    """
    A v1 provider implementation.

    This base class implements a checkbox-like provider object. Subclasses are
    only required to implement a single method that designates the base
    location for all other data.
    """

    def __init__(self, base_dir, name, description, secure):
        """
        Initialize the provider with the associated base directory.

        All of the typical v1 provider data is relative to this directory. It
        can be customized by subclassing and overriding the particular methods
        of the IProviderBackend1 class but that should not be necessary in
        normal operation.
        """
        self._base_dir = base_dir
        self._name = name
        self._description = description
        self._secure = secure

    @property
    def name(self):
        """
        name of this provider
        """
        return self._name

    @property
    def description(self):
        """
        description of this provider
        """
        return self._description

    @property
    def jobs_dir(self):
        """
        Return an absolute path of the jobs directory
        """
        return os.path.join(self._base_dir, "jobs")

    @property
    def bin_dir(self):
        """
        Return an absolute path of the bin directory

        .. note::
            The programs in that directory may not work without setting
            PYTHONPATH and CHECKBOX_SHARE.
        """
        return os.path.join(self._base_dir, "bin")

    @property
    def whitelists_dir(self):
        """
        Return an absolute path of the whitelist directory
        """
        return os.path.join(self._base_dir, "whitelists")

    @property
    def CHECKBOX_SHARE(self):
        """
        Return the required value of CHECKBOX_SHARE environment variable.

        .. note::
            This variable is only required by one script.
            It would be nice to remove this later on.
        """
        return self._base_dir

    @property
    def extra_PYTHONPATH(self):
        """
        Return additional entry for PYTHONPATH, if needed.

        This entry is required for CheckBox scripts to import the correct
        CheckBox python libraries.

        .. note::
            The result may be None
        """
        return None

    @property
    def secure(self):
        """
        flag indicating that this provider was loaded from the secure portion
        of PROVIDERPATH and thus can be used with the
        plainbox-trusted-launcher-1.
        """
        return self._secure

    def get_builtin_whitelists(self):
        logger.debug("Loading built-in whitelists...")
        whitelist_list = []
        try:
            items = os.listdir(self.whitelists_dir)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                items = []
            else:
                raise
        for name in items:
            if name.endswith(".whitelist"):
                whitelist_list.append(
                    WhiteList.from_file(os.path.join(
                        self.whitelists_dir, name)))
        return sorted(whitelist_list, key=lambda whitelist: whitelist.name)

    def get_builtin_jobs(self):
        logger.debug("Loading built-in jobs...")
        job_list = []
        try:
            items = os.listdir(self.jobs_dir)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                items = []
            else:
                raise
        for name in items:
            if name.endswith(".txt") or name.endswith(".txt.in"):
                job_list.extend(
                    self.load_jobs(
                        os.path.join(self.jobs_dir, name)))
        return sorted(job_list, key=lambda job: job.name)

    def get_all_executables(self):
        """
        Discover and return all executables offered by this provider
        """
        executable_list = []
        try:
            items = os.listdir(self.bin_dir)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                items = []
            else:
                raise
        for name in items:
            filename = os.path.join(self.bin_dir, name)
            if os.access(filename, os.F_OK | os.X_OK):
                executable_list.append(filename)
        return sorted(executable_list)

    def load_jobs(self, somewhere):
        """
        Load job definitions from somewhere
        """
        if isinstance(somewhere, str):
            # Load data from a file with the given name
            filename = somewhere
            with open(filename, 'rt', encoding='UTF-8') as stream:
                return self.load_jobs(stream)
        if isinstance(somewhere, io.TextIOWrapper):
            stream = somewhere
            logger.debug("Loading jobs definitions from %r...", stream.name)
            record_list = load_rfc822_records(stream)
            job_list = []
            for record in record_list:
                job = JobDefinition.from_rfc822_record(record)
                job._provider = self
                logger.debug("Loaded %r", job)
                job_list.append(job)
            return job_list
        else:
            raise TypeError(
                "Unsupported type of 'somewhere': {!r}".format(
                    type(somewhere)))


class IQNValidator(PatternValidator):
    """
    A validator for provider name.

    Provider names use a RFC3720 IQN-like identifiers composed of the follwing
    parts:

    * year
    * (dot separating the next section)
    * domain name
    * (colon separating the next section)
    * identifier

    Each of the fields has an informal definition below:

        year:
            four digit number
        domain name:
            identifiers spearated by dots, at least one dot has to be present
        identifier:
            `[a-z][a-z0-9-]*`
    """

    def __init__(self):
        super(IQNValidator, self).__init__(
            "[0-9]{4}\.[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+:[a-z][a-z0-9-]+")

    def __call__(self, variable, new_value):
        if super(IQNValidator, self).__call__(variable, new_value):
            return "must look like RFC3720 IQN"


class ExistingDirectoryValidator(IValidator):
    """
    A validator that checks that the value points to an existing directory
    """

    def __call__(self, variable, new_value):
        if not os.path.isdir(new_value):
            return "no such directory"


class AbsolutePathValidator(IValidator):
    """
    A validator that checks that the value is an absolute path
    """

    def __call__(self, variable, new_value):
        if not os.path.isabs(new_value):
            return "cannot be relative"


class Provider1Definition(Config):
    """
    A Config-like class for parsing plainbox provider definition files
    """

    location = Variable(
        section='PlainBox Provider',
        help_text="Base directory with provider data",
        validator_list=[
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    name = Variable(
        section='PlainBox Provider',
        help_text="Name of the provider",
        validator_list=[
            NotEmptyValidator(),
            IQNValidator(),
        ])

    description = Variable(
        section='PlainBox Provider',
        help_text="Description of the provider")


class Provider1PlugIn(IPlugIn):
    """
    A specialized IPlugIn that loads Provider1 instances from their defition
    files
    """

    def __init__(self, filename, definition_text):
        """
        Initialize the plug-in with the specified name and external object
        """
        definition = Provider1Definition()
        definition.read_string(definition_text)
        self._provider = Provider1(
            definition.location, definition.name, definition.description,
            secure=os.path.dirname(filename) == get_secure_PROVIDERPATH())

    def __repr__(self):
        return "<{!s} plugin_name:{!r}>".format(
            type(self).__name__, self.plugin_name)

    @property
    def plugin_name(self):
        """
        plugin name, the namespace of the provider
        """
        return self._provider.name

    @property
    def plugin_object(self):
        """
        plugin object, the actual Provider1 instance
        """
        return self._provider


def get_secure_PROVIDERPATH():
    """
    Computes the secure value for PROVIDERPATH.

    For the root-elevated trusted launcher PROVIDERPATH should contain one
    directory entry:

        * /usr/share/plainbox-providers-1
    """
    sys_wide = "/usr/share/plainbox-providers-1"
    return os.path.pathsep.join([sys_wide])


class Provider1PlugInCollection(FsPlugInCollection):
    """
    A collection of v1 provider plugins.

    This class is just like FsPlugInCollection but knows the proper arguments
    (PROVIDERPATH and the extension)
    """

    DEFAULT_PROVIDERPATH = get_secure_PROVIDERPATH()

    def __init__(self):
        providerpath = os.getenv("PROVIDERPATH", self.DEFAULT_PROVIDERPATH)
        super(Provider1PlugInCollection, self).__init__(
            providerpath, '.provider', wrapper=Provider1PlugIn)


# Collection of all providers
all_providers = Provider1PlugInCollection()
