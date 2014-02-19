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
:mod:`plainbox.impl.secure.providers.v1` -- Implementation of V1 provider
=========================================================================
"""

import errno
import itertools
import logging
import os

from plainbox.abc import IProvider1, IProviderBackend1
from plainbox.i18n import gettext as _
from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.config import Config, Variable
from plainbox.impl.secure.config import IValidator
from plainbox.impl.secure.config import NotEmptyValidator
from plainbox.impl.secure.config import NotUnsetValidator
from plainbox.impl.secure.config import PatternValidator
from plainbox.impl.secure.plugins import FsPlugInCollection
from plainbox.impl.secure.plugins import IPlugIn
from plainbox.impl.secure.plugins import PlugInError
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.rfc822 import FileTextSource
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.secure.rfc822 import load_rfc822_records


logger = logging.getLogger("plainbox.secure.providers.v1")


class WhiteListPlugIn(IPlugIn):
    """
    A specialized :class:`plainbox.impl.secure.plugins.IPlugIn` that loads
    :class:`plainbox.impl.secure.qualifiers.WhiteList` instances from a file.
    """

    def __init__(self, filename, text):
        """
        Initialize the plug-in with the specified name text
        """
        try:
            self._whitelist = WhiteList.from_string(text, filename=filename)
        except Exception as exc:
            raise PlugInError(
                _("Cannot load whitelist {!r}: {}").format(filename, exc))

    @property
    def plugin_name(self):
        """
        plugin name, the name of the WhiteList
        """
        return self._whitelist.name

    @property
    def plugin_object(self):
        """
        plugin object, the actual WhiteList instance
        """
        return self._whitelist


class JobDefinitionPlugIn(IPlugIn):
    """
    A specialized :class:`plainbox.impl.secure.plugins.IPlugIn` that loads a
    list of :class:`plainbox.impl.job.JobDefinition` instances from a file.
    """

    def __init__(self, filename, text, provider):
        """
        Initialize the plug-in with the specified name text
        """
        self._filename = filename
        self._job_list = []
        logger.debug(_("Loading jobs definitions from %r..."), filename)
        try:
            for record in load_rfc822_records(
                    text, source=FileTextSource(filename)):
                job = JobDefinition.from_rfc822_record(record)
                job._provider = provider
                self._job_list.append(job)
                logger.debug(_("Loaded %r"), job)
        except RFC822SyntaxError as exc:
            raise PlugInError(
                _("Cannot load job definitions from {!r}: {}").format(
                    filename, exc))

    @property
    def plugin_name(self):
        """
        plugin name, name of the file we loaded jobs from
        """
        return self._filename

    @property
    def plugin_object(self):
        """
        plugin object, a list of JobDefinition instances
        """
        return self._job_list


class Provider1(IProvider1, IProviderBackend1):
    """
    A v1 provider implementation.

    This base class implements a checkbox-like provider object. Subclasses are
    only required to implement a single method that designates the base
    location for all other data.
    """

    def __init__(self, base_dir, name, version, description, secure,
                 gettext_domain=None):
        """
        Initialize the provider with the associated base directory.

        All of the typical v1 provider data is relative to this directory. It
        can be customized by subclassing and overriding the particular methods
        of the IProviderBackend1 class but that should not be necessary in
        normal operation.
        """
        self._base_dir = base_dir
        self._name = name
        self._version = version
        self._description = description
        self._secure = secure
        self._gettext_domain = gettext_domain
        self._whitelist_collection = FsPlugInCollection(
            [self.whitelists_dir], ext=".whitelist", wrapper=WhiteListPlugIn)
        self._job_collection = FsPlugInCollection(
            [self.jobs_dir], ext=(".txt", ".txt.in"),
            wrapper=JobDefinitionPlugIn, provider=self)

    def __repr__(self):
        return "<{} name:{!r} base_dir:{!r}>".format(
            self.__class__.__name__, self.name, self.base_dir)

    @property
    def base_dir(self):
        """
        pathname to a directory with essential provider data

        This pathname is used for deriving :attr:`jobs_dir`, :attr:`bin_dir`
        and :attr:`whitelists_dir`.
        """
        return self._base_dir

    @property
    def name(self):
        """
        name of this provider
        """
        return self._name

    @property
    def version(self):
        """
        version of this provider
        """
        return self._version

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

    @property
    def gettext_domain(self):
        """
        the name of the gettext domain associated with this provider

        This value may be empty, in such case provider data cannot be localized
        for the user environment.
        """
        return self._gettext_domain

    def get_builtin_whitelists(self):
        """
        Load all the whitelists from :attr:`whitelists_dir` and return them

        This method looks at the whitelist directory and loads all files ending
        with .whitelist as a WhiteList object.

        :returns:
            A list of :class:`~plainbox.impl.secure.qualifiers.WhiteList`
            objects sorted by
            :attr:`plainbox.impl.secure.qualifiers.WhiteList.name`.
        :raises IOError, OSError:
            if there were any problems accessing files or directories.  Note
            that OSError is silently ignored when the `whitelists_dir`
            directory is missing.
        """
        self._whitelist_collection.load()
        if self._whitelist_collection.problem_list:
            raise self._whitelist_collection.problem_list[0]
        else:
            return sorted(self._whitelist_collection.get_all_plugin_objects(),
                          key=lambda whitelist: whitelist.name)

    def get_builtin_jobs(self):
        """
        Load and parse all of the job definitions of this provider.

        :returns:
            A sorted list of JobDefinition objects
        :raises RFC822SyntaxError:
            if any of the loaded files was not valid RFC822
        :raises IOError, OSError:
            if there were any problems accessing files or directories.
            Note that OSError is silently ignored when the `jobs_dir`
            directory is missing.

        ..note::
            This method should not be used anymore. Consider transitioning your
            code to :meth:`load_all_jobs()` which is more reliable.
        """
        job_list, problem_list = self.load_all_jobs()
        if problem_list:
            raise problem_list[0]
        else:
            return job_list

    def load_all_jobs(self):
        """
        Load and parse all of the job definitions of this provider.

        Unlike :meth:`get_builtin_jobs()` this method does not stop after the
        first problem encountered and instead collects all of the problems into
        a list which is returned alongside the job list.

        :returns:
            Pair (job_list, problem_list) where each job_list is a sorted list
            of JobDefinition objects and each item from problem_list is an
            exception.
        """
        self._job_collection.load()
        job_list = sorted(
            itertools.chain(
                *self._job_collection.get_all_plugin_objects()),
            key=lambda job: job.id)
        problem_list = self._job_collection.problem_list
        return job_list, problem_list

    def get_all_executables(self):
        """
        Discover and return all executables offered by this provider

        :returns:
            list of executable names (without the full path)
        :raises IOError, OSError:
            if there were any problems accessing files or directories. Note
            that OSError is silently ignored when the `bin_dir` directory is
            missing.
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
            "^[0-9]{4}\.[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+:[a-z][a-z0-9-]*$")

    def __call__(self, variable, new_value):
        if super(IQNValidator, self).__call__(variable, new_value):
            return _("must look like RFC3720 IQN")


class VersionValidator(PatternValidator):
    """
    A validator for provider provider version.

    Provider version must be a sequence of non-negative numbers separated by
    dots. At most one version number must be present, which may be followed by
    any sub-versions.
    """

    def __init__(self):
        super().__init__("^[0-9]+(\.[0-9]+)*$")

    def __call__(self, variable, new_value):
        if super().__call__(variable, new_value):
            return _("must be a sequence of digits separated by dots")


class ExistingDirectoryValidator(IValidator):
    """
    A validator that checks that the value points to an existing directory
    """

    def __call__(self, variable, new_value):
        if not os.path.isdir(new_value):
            return _("no such directory")


class AbsolutePathValidator(IValidator):
    """
    A validator that checks that the value is an absolute path
    """

    def __call__(self, variable, new_value):
        if not os.path.isabs(new_value):
            return _("cannot be relative")


class Provider1Definition(Config):
    """
    A Config-like class for parsing plainbox provider definition files
    """

    location = Variable(
        section='PlainBox Provider',
        help_text=_("Base directory with provider data"),
        validator_list=[
            NotUnsetValidator(),
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    name = Variable(
        section='PlainBox Provider',
        help_text=_("Name of the provider"),
        validator_list=[
            NotUnsetValidator(),
            NotEmptyValidator(),
            IQNValidator(),
        ])

    version = Variable(
        section='PlainBox Provider',
        help_text=_("Version of the provider"),
        validator_list=[
            NotUnsetValidator(),
            NotEmptyValidator(),
            VersionValidator(),
        ])

    description = Variable(
        section='PlainBox Provider',
        help_text=_("Description of the provider"))

    gettext_domain = Variable(
        section='PlainBox Provider',
        default="",
        help_text=_("Name of the gettext domain for translations"))


class Provider1PlugIn(IPlugIn):
    """
    A specialized IPlugIn that loads Provider1 instances from their definition
    files
    """

    def __init__(self, filename, definition_text):
        """
        Initialize the plug-in with the specified name and external object
        """
        definition = Provider1Definition()
        # Load the provider definition
        definition.read_string(definition_text)
        # any validation issues prevent plugin from being used
        if definition.problem_list:
            # take the earliest problem and report it
            exc = definition.problem_list[0]
            raise PlugInError(
                _("Problem in provider definition, field {!a}: {}").format(
                    exc.variable.name, exc.message))
        # Initialize the provider object
        self._provider = Provider1(
            definition.location,
            definition.name,
            definition.version,
            definition.description,
            secure=os.path.dirname(filename) in get_secure_PROVIDERPATH_list(),
            gettext_domain=definition.gettext_domain)

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


def get_secure_PROVIDERPATH_list():
    """
    Computes the secure value of PROVIDERPATH

    This value is used by `plainbox-trusted-launcher-1` executable to discover
    all secure providers.

    :returns:
        A list of two strings:
        * `/usr/local/share/plainbox-providers-1`
        * `/usr/share/plainbox-providers-1`
    """
    return ["/usr/local/share/plainbox-providers-1",
            "/usr/share/plainbox-providers-1"]


class SecureProvider1PlugInCollection(FsPlugInCollection):
    """
    A collection of v1 provider plugins.

    This FsPlugInCollection subclass carries proper, built-in defaults, that
    make loading providers easier.

    This particular class loads providers from the system-wide managed
    locations. This defines the security boundary, as if someone can compromise
    those locations then they already own the corresponding system. In
    consequence this plug in collection does not respect ``PROVIDERPATH``, it
    cannot be customized to load provider definitions from any other location.
    This feature is supported by the
    :class:`plainbox.impl.providers.v1.InsecureProvider1PlugInCollection`
    """

    def __init__(self):
        dir_list = get_secure_PROVIDERPATH_list()
        super().__init__(dir_list, '.provider', wrapper=Provider1PlugIn)


# Collection of all providers
all_providers = SecureProvider1PlugInCollection()
