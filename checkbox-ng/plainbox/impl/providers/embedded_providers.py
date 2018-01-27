# This file is part of Checkbox.
#
# Copyright 2014-2017 Canonical Ltd.
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
from importlib.machinery import SourceFileLoader
import os

from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.plugins import FsPlugInCollection
from plainbox.impl.secure.plugins import now
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.providers.v1 import Provider1Definition
from plainbox.impl.secure.providers.v1 import Provider1PlugIn


class ManagePyProvider1PlugIn(Provider1PlugIn):
    """
    Provider1PlugIn that is built from manage.py file.
    """

    def __init__(self, filename, file_contents, load_time, *, validate=None,
                 validation_kwargs=None, check=None, context=None):
        """
        Initialize plug-in and create provider from definition extracted
        from manage.py pointed by `filename`
        """
        self._load_time = load_time
        # override provider_manager.setup() to capture setup's parameters
        setup_kwargs = []
        start_time = now()

        def fake_setup(**kwargs):
            setup_kwargs.append(kwargs)

        from plainbox import provider_manager
        provider_manager.setup = fake_setup

        loader = SourceFileLoader('manage', filename)
        loader.load_module()
        location = os.path.dirname(os.path.abspath(filename))
        if len(setup_kwargs) < 1:
            # did not load any provider from given manage.py
            # creating empty definition
            definition = Provider1Definition()
        else:
            setup_kwargs = setup_kwargs.pop()
            definition = Provider1Definition()
            definition.location = location
            definition.name = setup_kwargs.get('name', None)
            definition.namespace = setup_kwargs.get('namespace', Unset)
            definition.version = setup_kwargs.get('version', None)
            definition.description = setup_kwargs.get('description', None)
            definition.gettext_domain = setup_kwargs.get(
                'gettext_domain', Unset)
        self._provider = Provider1.from_definition(
            definition, secure=False, validate=validate,
            validation_kwargs=validation_kwargs, check=check, context=context)
        self._wrap_time = now() - start_time

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

    @property
    def plugin_load_time(self) -> float:
        """
        time, in fractional seconds, that was needed to load the provider
        definition file from the file system
        """
        return self._load_time

    @property
    def plugin_wrap_time(self) -> float:
        """
        time, in fractional seconds, that was needed to load the provider from
        the definition text
        """
        return self._wrap_time


class EmbeddedProvider1PlugInCollection(FsPlugInCollection):
    """
    A collection of v1 provider plugins loaded from 'manage.py'  files.

    """
    def __init__(self, path, **kwargs):
        """
        Initiates collection with all providers loaded from manage.py files
        found in `path` and subdirectories.
        """
        # get all manage.py files to load providers from
        super().__init__(
            [path], 'manage.py', recursive=True, load=True,
            wrapper=ManagePyProvider1PlugIn, **kwargs)
