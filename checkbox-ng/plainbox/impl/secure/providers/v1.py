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
:mod:`plainbox.impl.secure.providers.v1` -- Implementation of V1 provider
=========================================================================
"""
import collections
import gettext
import logging
import os

from plainbox.abc import IProvider1
from plainbox.i18n import gettext as _
from plainbox.impl.secure.config import Config, Variable
from plainbox.impl.secure.config import (
    ValidationError as ConfigValidationError)
from plainbox.impl.secure.config import IValidator
from plainbox.impl.secure.config import NotEmptyValidator
from plainbox.impl.secure.config import NotUnsetValidator
from plainbox.impl.secure.config import PatternValidator
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.plugins import FsPlugInCollection
from plainbox.impl.secure.plugins import LazyFsPlugInCollection
from plainbox.impl.secure.plugins import PlugIn
from plainbox.impl.secure.plugins import PlugInError
from plainbox.impl.secure.plugins import now
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.rfc822 import FileTextSource
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.secure.rfc822 import load_rfc822_records
from plainbox.impl.unit import all_units
from plainbox.impl.unit.file import FileRole
from plainbox.impl.unit.file import FileUnit
from plainbox.impl.unit.testplan import TestPlanUnit
from plainbox.impl.validation import Severity
from plainbox.impl.validation import ValidationError


logger = logging.getLogger("plainbox.secure.providers.v1")


class ProviderContentPlugIn(PlugIn):
    """
    PlugIn class for loading provider content.

    Provider content comes in two shapes and sizes:
        - units (of any kind)
        - whitelists

    The actual logic on how to load everything is encapsulated in
    :meth:`wrap()` though its return value is not so useful.

    :attr unit_list:
        The list of loaded units
    :attr whitelist_list:
        The list of loaded whitelists
    """

    def __init__(self, filename, text, load_time, provider, *,
                 validate=False, validation_kwargs=None,
                 check=True, context=None):
        start_time = now()
        try:
            # Inspect the file
            inspect_result = self.inspect(
                filename, text, provider,
                validate, validation_kwargs or {},  # legacy validation
                check, context  # modern validation
            )
        except PlugInError as exc:
            raise exc
        except Exception as exc:
            raise PlugInError(_("Cannot load {!r}: {}").format(filename, exc))
        wrap_time = now() - start_time
        super().__init__(filename, inspect_result, load_time, wrap_time)
        self.unit_list = []
        self.whitelist_list = []
        # And load all of the content from that file
        self.unit_list.extend(self.discover_units(
            inspect_result, filename, text, provider))
        self.whitelist_list.extend(self.discover_whitelists(
            inspect_result, filename, text, provider))

    def inspect(self, filename: str, text: str, provider: "Provider1",
                validate: bool, validation_kwargs: "Dict[str, Any]", check:
                bool, context: "???") -> "Any":
        """
        Interpret and wrap the content of the filename as whatever is
        appropriate. The return value of this class becomes the
        :meth:`plugin_object`

        .. note::
            This method must *not* access neither :attr:`unit_list` nor
            :attr:`whitelist_list`. If needed, it can collect its own state in
            private instance attributes.
        """

    def discover_units(
        self, inspect_result: "Any", filename: str, text: str,
        provider: "Provider1"
    ) -> "Iterable[Unit]":
        """
        Discover all units that were loaded by this plug-in

        :param wrap_result:
            whatever was returned on the call to :meth:`wrap()`.
        :returns:
            an iterable of units.

        .. note::
            this method is always called *after* :meth:`wrap()`.
        """
        yield self.make_file_unit(filename, provider)

    def discover_whitelists(
        self, inspect_result: "Any", filename: str, text: str,
        provider: "Provider1"
    ) -> "Iterable[WhiteList]":
        """
        Discover all whitelists that were loaded by this plug-in

        :param wrap_result:
            whatever was returned on the call to :meth:`wrap()`.
        :returns:
            an iterable of whitelists.

        .. note::
            this method is always called *after* :meth:`wrap()`.
        """
        return ()

    def make_file_unit(self, filename, provider, role=None, base=None):
        if role is None or base is None:
            role, base, plugin_cls = provider.classify(filename)
        return FileUnit({
            'unit': FileUnit.Meta.name,
            'path': filename,
            'base': base,
            'role': role,
        }, origin=Origin(FileTextSource(filename)), provider=provider,
            virtual=True)


class WhiteListPlugIn(ProviderContentPlugIn):
    """
    A specialized :class:`plainbox.impl.secure.plugins.IPlugIn` that loads
    :class:`plainbox.impl.secure.qualifiers.WhiteList` instances from a file.
    """

    def inspect(self, filename: str, text: str, provider: "Provider1",
                validate: bool, validation_kwargs: "Dict[str, Any]", check:
                bool, context: "???") -> "WhiteList":
        if provider is not None:
            implicit_namespace = provider.namespace
        else:
            implicit_namespace = None
        origin = Origin(FileTextSource(filename), 1, text.count('\n'))
        return WhiteList.from_string(
            text, filename=filename, origin=origin,
            implicit_namespace=implicit_namespace)

    def discover_units(
        self, inspect_result: "WhiteList", filename: str, text: str,
        provider: "Provider1"
    ) -> "Iterable[Unit]":
        if provider is not None:
            yield self.make_file_unit(
                filename, provider,
                # NOTE: don't guess what this file is for
                role=FileRole.legacy_whitelist, base=provider.whitelists_dir)
            yield self.make_test_plan_unit(filename, text, provider)

    def discover_whitelists(
        self, inspect_result: "WhiteList", filename: str, text: str,
        provider: "Provider1"
    ) -> "Iterable[WhiteList]":
        yield inspect_result

    def make_test_plan_unit(self, filename, text, provider):
        name = os.path.basename(os.path.splitext(filename)[0])
        origin = Origin(FileTextSource(filename), 1, text.count('\n'))
        field_offset_map = {'include': 0}
        return TestPlanUnit({
            'unit': TestPlanUnit.Meta.name,
            'id': name,
            'name': name,
            'include': str(text),  # delazify content
        }, origin=origin, provider=provider, field_offset_map=field_offset_map,
            virtual=True)

    # NOTE: This version of __init__() exists solely so that provider can
    # default to None. This is still used in some places and must be supported.
    def __init__(self, filename, text, load_time, provider=None, *,
                 validate=False, validation_kwargs=None,
                 check=True, context=None):
        super().__init__(
            filename, text, load_time, provider, validate=validate,
            validation_kwargs=validation_kwargs, check=check, context=context)

    # NOTE: this version of plugin_name() is just for legacy code support
    @property
    def plugin_name(self):
        """
        plugin name, the name of the WhiteList
        """
        return self.plugin_object.name


class UnitPlugIn(ProviderContentPlugIn):
    """
    A specialized :class:`plainbox.impl.secure.plugins.IPlugIn` that loads a
    list of :class:`plainbox.impl.unit.Unit` instances from a file.
    """

    def inspect(
        self, filename: str, text: str, provider: "Provider1", validate: bool,
        validation_kwargs: "Dict[str, Any]", check: bool, context: "???"
    ) -> "Any":
        """
        Load all units from their PXU representation.

        :param filename:
            Name of the file with unit definitions
        :param text:
            Full text of the file with unit definitions (lazy)
        :param provider:
            A provider object to which those units belong to
        :param validate:
            Enable unit validation. Incorrect unit definitions will not be
            loaded and will abort the process of loading of the remainder of
            the jobs.  This is ON by default to prevent broken units from being
            used. This is a keyword-only argument.
        :param validation_kwargs:
            Keyword arguments to pass to the Unit.validate().  Note, this is a
            single argument. This is a keyword-only argument.
        :param check:
            Enable unit checking. Incorrect unit definitions will not be loaded
            and will abort the process of loading of the remainder of the jobs.
            This is OFF by default to prevent broken units from being used.
            This is a keyword-only argument.
        :param context:
            If checking, use this validation context.
        """
        logger.debug(_("Loading units from %r..."), filename)
        try:
            records = load_rfc822_records(
                text, source=FileTextSource(filename))
        except RFC822SyntaxError as exc:
            raise PlugInError(
                _("Cannot load job definitions from {!r}: {}").format(
                    filename, exc))
        unit_list = []
        for record in records:
            unit_name = record.data.get('unit', 'job')
            try:
                unit_cls = self._get_unit_cls(unit_name)
            except KeyError:
                raise PlugInError(
                    _("Unknown unit type: {!r}").format(unit_name))
            try:
                unit = unit_cls.from_rfc822_record(record, provider)
            except ValueError as exc:
                raise PlugInError(
                    _("Cannot define unit from record {!r}: {}").format(
                        record, exc))
            if check:
                for issue in unit.check(context=context, live=True):
                    if issue.severity is Severity.error:
                        raise PlugInError(
                            _("Problem in unit definition, {}").format(issue))
            if validate:
                try:
                    unit.validate(**validation_kwargs)
                except ValidationError as exc:
                    raise PlugInError(
                        _("Problem in unit definition, field {}: {}").format(
                            exc.field, exc.problem))
            unit_list.append(unit)
            logger.debug(_("Loaded %r"), unit)
        return unit_list

    def discover_units(
        self, inspect_result: "List[Unit]", filename: str, text: str,
        provider: "Provider1"
    ) -> "Iterable[Unit]":
        for unit in inspect_result:
            yield unit
        yield self.make_file_unit(filename, provider)

    def discover_whitelists(
        self, inspect_result: "List[Unit]", filename: str, text: str,
        provider: "Provider1"
    ) -> "Iterable[WhiteList]":
        for unit in (unit for unit in inspect_result
                     if unit.Meta.name == 'test plan'):
            yield WhiteList(
                unit.include, name=unit.partial_id, origin=unit.origin,
                implicit_namespace=unit.provider.namespace)

    # NOTE: this version of plugin_object() is just for legacy code support
    @property
    def plugin_object(self):
        return self.unit_list

    @staticmethod
    def _get_unit_cls(unit_name):
        """
        Get a class that implements the specified unit
        """
        # TODO: transition to lazy plugin collection
        all_units.load()
        return all_units.get_by_name(unit_name).plugin_object


class ProviderContentEnumerator:
    """
    Support class for enumerating provider content.

    The only role of this class is to expose a plug in collection that can
    enumerate all of the files reachable from a provider. This collection
    is consumed by other parts of provider loading machinery.

    Since it is a stock plug in collection it can be easily "mocked" to provide
    alternate content without involving modifications of the real file system.

    .. note::
        This class is automatically instantiated by :class:`Provider1`. The
        :meth:`content_collection` property is exposed as
        :meth:`Provider1.content_collection`.
    """

    def __init__(self, provider: "Provider1"):
        """
        Initialize a new provider content enumerator

        :param provider:
            The associated provider
        """
        # NOTE: This code tries to account for two possible layouts. In one
        # layout we don't have the base directory and everything is spread
        # across the filesystem. This is how a packaged provider looks like.
        # The second layout is the old flat layout that is not being used
        # anymore. The only modern exception is when working with a provider
        # from source. To take that into account, the src_dir and build_bin_dir
        # are optional.
        if provider.base_dir:
            dir_list = [provider.base_dir]
            if provider.src_dir:
                dir_list.append(provider.src_dir)
                # NOTE: in source layout we may also see virtual executables
                # that are not loaded yet. Those are listed by
                # "$src_dir/EXECUTABLES"
            if provider.build_bin_dir:
                dir_list.append(provider.build_bin_dir)
            if provider.build_mo_dir:
                dir_list.append(provider.build_mo_dir)
        else:
            dir_list = []
            if provider.units_dir:
                dir_list.append(provider.units_dir)
            if provider.jobs_dir:
                dir_list.append(provider.jobs_dir)
            if provider.data_dir:
                dir_list.append(provider.data_dir)
            if provider.bin_dir:
                dir_list.append(provider.bin_dir)
            if provider.locale_dir:
                dir_list.append(provider.locale_dir)
            if provider.whitelists_dir:
                dir_list.append(provider.whitelists_dir)
        # Find all the files that belong to a provider
        self._content_collection = LazyFsPlugInCollection(
            dir_list, ext=None, recursive=True)

    @property
    def content_collection(self) -> "IPlugInCollection":
        """
        An plugin collection that enumerates all of the files in the provider.

        This collections exposes all of the files in a provider. It can also be
        mocked for easier testing. It is the only part of the provider codebase
        that tries to discover data in a file system.

        .. note::
            By default the collection is **not** loaded. Make sure to call
            ``.load()`` to see the actual data. This is, again, a way to
            simplify testing and to de-couple it from file-system activity.
        """
        return self._content_collection


class ProviderContentClassifier:
    """
    Support class for classifying content inside a provider.

    The primary role of this class is to come up with the role of each file
    inside the provider. That includes all files reachable from any of the
    directories that constitute a provider definition. In addition, each file
    is associated with a *base directory*. This directory can be used to
    re-construct the same provider at a different location or in a different
    layout.

    The secondary role is to provide a hint on what PlugIn to use to load such
    content (as units). In practice the majority of files are loaded with the
    :class:`UnitPlugIn` class. Legacy ``.whitelist`` files are loaded with the
    :class:`WhiteListPlugIn` class instead. All other files are handled by the
    :class:`ProviderContentPlugIn`.

    .. note::
        This class is automatically instantiated by :class:`Provider1`. The
        :meth:`classify` method is exposed as :meth:`Provider1.classify()`.
    """
    LEGAL_SET = frozenset(['COPYING', 'COPYING.LESSER', 'LICENSE'])
    DOC_SET = frozenset(['README', 'README.md', 'README.rst', 'README.txt'])

    def __init__(self, provider: "Provider1"):
        """
        Initialize a new provider content classifier

        :param provider:
            The associated provider
        """
        self.provider = provider
        self._classify_fn_list = None
        self._EXECUTABLES = None

    def classify(self, filename: str) -> "Tuple[Symbol, str, type]":
        """
        Classify a file belonging to the provider

        :param filename:
            Full pathname of the file to classify
        :returns:
            A tuple of information about the file. The first element is the
            :class:`FileRole` symbol that describes the role of the file. The
            second element is the base path of the file. It can be subtracted
            from the actual filename to obtain a relative directory where the
            file needs to be located in case of provider re-location. The last,
            third element is the plug-in class that can be used to load units
            from that file.
        :raises ValueError:
            If the file cannot be classified. This can only happen if the file
            is not in any way related to the provider. All (including random
            junk) files can be classified correctly, as long as they are inside
            one of the well-known directories.
        """
        for fn in self.classify_fn_list:
            result = fn(filename)
            if result is not None:
                return result
        else:
            raise ValueError("Unable to classify: {!r}".format(filename))

    @property
    def classify_fn_list(
        self
    ) -> "List[Callable[[str], Tuple[Symbol, str, type]]]":
        """
        List of functions that aid in the classification process.
        """
        if self._classify_fn_list is None:
            self._classify_fn_list = self._get_classify_fn_list()
        return self._classify_fn_list

    def _get_classify_fn_list(
        self
    ) -> "List[Callable[[str], Tuple[Symbol, str, type]]]":
        """
        Get a list of function that can classify any file reachable from our
        provider. The returned function list depends on which directories are
        present.

        :returns:
            A list of functions ``fn(filename) -> (Symbol, str, plugin_cls)``
            where the return value is a tuple (file_role, base_dir, type).
            The plugin_cls can be used to find all of the units stored in that
            file.
        """
        classify_fn_list = []
        if self.provider.jobs_dir:
            classify_fn_list.append(self._classify_pxu_jobs)
        if self.provider.units_dir:
            classify_fn_list.append(self._classify_pxu_units)
        if self.provider.whitelists_dir:
            classify_fn_list.append(self._classify_whitelist)
        if self.provider.data_dir:
            classify_fn_list.append(self._classify_data)
        if self.provider.bin_dir:
            classify_fn_list.append(self._classify_exec)
        if self.provider.build_bin_dir:
            classify_fn_list.append(self._classify_built_exec)
        if self.provider.build_mo_dir:
            classify_fn_list.append(self._classify_built_i18n)
        if self.provider.build_dir:
            classify_fn_list.append(self._classify_build)
        if self.provider.po_dir:
            classify_fn_list.append(self._classify_po)
        if self.provider.src_dir:
            classify_fn_list.append(self._classify_src)
        if self.provider.base_dir:
            classify_fn_list.append(self._classify_legal)
            classify_fn_list.append(self._classify_docs)
            classify_fn_list.append(self._classify_manage_py)
            classify_fn_list.append(self._classify_vcs)
        # NOTE: this one always has to be last
        classify_fn_list.append(self._classify_unknown)
        return classify_fn_list

    def _get_EXECUTABLES(self):
        assert self.provider.src_dir is not None
        hint_file = os.path.join(self.provider.src_dir, 'EXECUTABLES')
        if os.path.isfile(hint_file):
            with open(hint_file, "rt", encoding='UTF-8') as stream:
                return frozenset(line.strip() for line in stream)
        else:
            return frozenset()

    @property
    def EXECUTABLES(self) -> "Set[str]":
        """
        A set of executables that are expected to be built from source.
        """
        if self._EXECUTABLES is None:
            self._EXECUTABLES = self._get_EXECUTABLES()
        return self._EXECUTABLES

    def _classify_pxu_jobs(self, filename: str):
        """ classify certain files in jobs_dir as unit source"""
        if filename.startswith(self.provider.jobs_dir):
            ext = os.path.splitext(filename)[1]
            if ext in (".txt", ".in", ".pxu"):
                return (FileRole.unit_source, self.provider.jobs_dir,
                        UnitPlugIn)

    def _classify_pxu_units(self, filename: str):
        """ classify certain files in units_dir as unit source"""
        if filename.startswith(self.provider.units_dir):
            ext = os.path.splitext(filename)[1]
            # TODO: later on just let .pxu files in the units_dir
            if ext in (".txt", ".txt.in", ".pxu"):
                return (FileRole.unit_source, self.provider.units_dir,
                        UnitPlugIn)

    def _classify_whitelist(self, filename: str):
        """ classify .whitelist files in whitelist_dir as whitelist """
        if (filename.startswith(self.provider.whitelists_dir)
                and filename.endswith(".whitelist")):
            return (FileRole.legacy_whitelist, self.provider.whitelists_dir,
                    WhiteListPlugIn)

    def _classify_data(self, filename: str):
        """ classify files in data_dir as data """
        if filename.startswith(self.provider.data_dir):
            return (FileRole.data, self.provider.data_dir,
                    ProviderContentPlugIn)

    def _classify_exec(self, filename: str):
        """ classify files in bin_dir as scripts/executables """
        if (filename.startswith(self.provider.bin_dir)
                and os.access(filename, os.F_OK | os.X_OK)):
            with open(filename, 'rb') as stream:
                chunk = stream.read(2)
            role = FileRole.script if chunk == b'#!' else FileRole.binary
            return (role, self.provider.bin_dir, ProviderContentPlugIn)

    def _classify_built_exec(self, filename: str):
        """ classify files in build_bin_dir as scripts/executables """
        if (filename.startswith(self.provider.build_bin_dir)
                and os.access(filename, os.F_OK | os.X_OK)
                and os.path.basename(filename) in self.EXECUTABLES):
            with open(filename, 'rb') as stream:
                chunk = stream.read(2)
            role = FileRole.script if chunk == b'#!' else FileRole.binary
            return (role, self.provider.build_bin_dir, ProviderContentPlugIn)

    def _classify_built_i18n(self, filename: str):
        """ classify files in build_mo_dir as i18n """
        if (filename.startswith(self.provider.build_mo_dir)
                and os.path.splitext(filename)[1] == '.mo'):
            return (FileRole.i18n, self.provider.build_bin_dir,
                    ProviderContentPlugIn)

    def _classify_build(self, filename: str):
        """ classify anything in build_dir as a build artefact """
        if filename.startswith(self.provider.build_dir):
            return (FileRole.build, self.provider.build_dir, None)

    def _classify_legal(self, filename: str):
        """ classify file as a legal document """
        if os.path.basename(filename) in self.LEGAL_SET:
            return (FileRole.legal, self.provider.base_dir,
                    ProviderContentPlugIn)

    def _classify_docs(self, filename: str):
        """ classify certain files as documentation """
        if os.path.basename(filename) in self.DOC_SET:
            return (FileRole.docs, self.provider.base_dir,
                    ProviderContentPlugIn)

    def _classify_manage_py(self, filename: str):
        """ classify the manage.py file """
        if os.path.join(self.provider.base_dir, 'manage.py') == filename:
            return (FileRole.manage_py, self.provider.base_dir, None)

    def _classify_po(self, filename: str):
        if (os.path.dirname(filename) == self.provider.po_dir
            and (os.path.splitext(filename)[1] in ('.po', '.pot')
                 or os.path.basename(filename) == 'POTFILES.in')):
            return (FileRole.src, self.provider.base_dir, None)

    def _classify_src(self, filename: str):
        if filename.startswith(self.provider.src_dir):
            return (FileRole.src, self.provider.base_dir, None)

    def _classify_vcs(self, filename: str):
        if os.path.basename(filename) in ('.gitignore', '.bzrignore'):
            return (FileRole.vcs, self.provider.base_dir, None)
        head = filename
        # NOTE: first condition is for correct cases, the rest are for broken
        # cases that may be caused if we get passed some garbage argument.
        while head != self.provider.base_dir and head != '' and head != '/':
            head, tail = os.path.split(head)
            if tail in ('.git', '.bzr'):
                return (FileRole.vcs, self.provider.base_dir, None)

    def _classify_unknown(self, filename: str):
        """ classify anything as an unknown file """
        return (FileRole.unknown, self.provider.base_dir, None)


class ProviderContentLoader:
    """
    Support class for enumerating provider content.

    The only role of this class is to expose a plug in collection that can
    enumerate all of the files reachable from a provider. This collection
    is consumed by other parts of provider loading machinery.

    Since it is a stock plug in collection it can be easily "mocked" to provide
    alternate content without involving modifications of the real file system.

    .. note::
        This class is automatically instantiated by :class:`Provider1`. All
        four attributes of this class are directly exposed as properties on the
        provider object.

    :attr provider:
        The provider back-reference
    :attr is_loaded:
        Flag indicating if the content loader has loaded all of the content
    :attr unit_list:
        A list of loaded whitelist objects
    :attr problem_list:
        A list of problems experienced while loading any of the content
    :attr path_map:
        A dictionary mapping from the path of each file to the list of units
        stored there.
    :attr id_map:
        A dictionary mapping from the identifier of each unit to the list of
        units that have that identifier.
    """

    def __init__(self, provider):
        self.provider = provider
        self.is_loaded = False
        self.unit_list = []
        self.whitelist_list = []
        self.problem_list = []
        self.path_map = collections.defaultdict(list)  # path -> list(unit)
        self.id_map = collections.defaultdict(list)  # id -> list(unit)

    def load(self, plugin_kwargs):
        logger.info("Loading content for provider %s", self.provider)
        self.provider.content_collection.load()
        for file_plugin in self.provider.content_collection.get_all_plugins():
            filename = file_plugin.plugin_name
            text = file_plugin.plugin_object
            self._load_file(filename, text, plugin_kwargs)
        self.problem_list.extend(self.provider.content_collection.problem_list)
        self.is_loaded = True

    def _load_file(self, filename, text, plugin_kwargs):
        # NOTE: text is lazy, call str() or iter() to see the real content This
        # prevents us from trying to read binary blobs.
        classification = self.provider.classify(filename)
        role, base_dir, plugin_cls = classification
        if plugin_cls is None:
            return
        try:
            plugin = plugin_cls(
                filename, text, 0, self.provider, **plugin_kwargs)
        except PlugInError as exc:
            self.problem_list.append(exc)
        else:
            self.unit_list.extend(plugin.unit_list)
            self.whitelist_list.extend(plugin.whitelist_list)
            for unit in plugin.unit_list:
                if hasattr(unit.Meta.fields, 'id'):
                    self.id_map[unit.id].append(unit)
                if hasattr(unit.Meta.fields, 'path'):
                    self.path_map[unit.path].append(unit)


class Provider1(IProvider1):
    """
    A v1 provider implementation.

    A provider is a container of jobs and whitelists. It provides additional
    meta-data and knows about location of essential directories to both load
    structured data and provide runtime information for job execution.

    Providers are normally loaded with :class:`Provider1PlugIn`, due to the
    number of fields involved in basic initialization.
    """

    def __init__(self, name, namespace, version, description, secure,
                 gettext_domain, units_dir, jobs_dir, whitelists_dir, data_dir,
                 bin_dir, locale_dir, base_dir, *, validate=False,
                 validation_kwargs=None, check=True, context=None):
        """
        Initialize a provider with a set of meta-data and directories.

        :param name:
            provider name / ID

        :param namespace:
            provider namespace

        :param version:
            provider version

        :param description:
            provider version

            This is the untranslated version of this field. Implementations may
            obtain the localized version based on the gettext_domain property.

        :param secure:
            secure bit

            When True jobs from this provider should be available via the
            trusted launcher mechanism. It should be set to True for
            system-wide installed providers.

        :param gettext_domain:
            gettext domain that contains translations for this provider

        :param units_dir:
            path of the directory with unit definitions

        :param jobs_dir:
            path of the directory with job definitions

        :param whitelists_dir:
            path of the directory with whitelists definitions (aka test-plans)

        :param data_dir:
            path of the directory with files used by jobs at runtime

        :param bin_dir:
            path of the directory with additional executables

        :param locale_dir:
            path of the directory with locale database (translation catalogs)

        :param base_dir:
            path of the directory with (perhaps) all of jobs_dir,
            whitelists_dir, data_dir, bin_dir, locale_dir. This may be None.
            This is also the effective value of $CHECKBOX_SHARE

        :param validate:
            Enable job validation. Incorrect job definitions will not be loaded
            and will abort the process of loading of the remainder of the jobs.
            This is ON by default to prevent broken job definitions from being
            used. This is a keyword-only argument.

        :param validation_kwargs:
            Keyword arguments to pass to the JobDefinition.validate().  Note,
            this is a single argument. This is a keyword-only argument.
        """
        # Meta-data
        if namespace is None:
            namespace = name.split(':', 1)[0]
            self._has_dedicated_namespace = False
        else:
            self._has_dedicated_namespace = True
        self._name = name
        self._namespace = namespace
        self._version = version
        self._description = description
        self._secure = secure
        self._gettext_domain = gettext_domain
        # Directories
        self._units_dir = units_dir
        self._jobs_dir = jobs_dir
        self._whitelists_dir = whitelists_dir
        self._data_dir = data_dir
        self._bin_dir = bin_dir
        self._locale_dir = locale_dir
        self._base_dir = base_dir
        # Create support classes
        self._enumerator = ProviderContentEnumerator(self)
        self._classifier = ProviderContentClassifier(self)
        self._loader = ProviderContentLoader(self)
        self._load_kwargs = {
            'validate': validate,
            'validation_kwargs': validation_kwargs,
            'check': check,
            'context': context,
        }
        # Setup provider specific i18n
        self._setup_translations()
        logger.info("Provider initialized %s", self)

    def _ensure_loaded(self):
        if not self._loader.is_loaded:
            self._loader.load(self._load_kwargs)

    def _load_whitelists(self):
        self._ensure_loaded()

    def _load_units(self, validate, validation_kwargs, check, context):
        self._ensure_loaded()

    def _setup_translations(self):
        if self._gettext_domain and self._locale_dir:
            gettext.bindtextdomain(self._gettext_domain, self._locale_dir)

    @classmethod
    def from_definition(cls, definition, secure, *,
                        validate=False, validation_kwargs=None, check=True,
                        context=None):
        """
        Initialize a provider from Provider1Definition object

        :param definition:
            A Provider1Definition object to use as reference
        :param secure:
            Value of the secure flag. This cannot be expressed by a definition
            object.
        :param validate:
            Enable job validation. Incorrect job definitions will not be loaded
            and will abort the process of loading of the remainder of the jobs.
            This is ON by default to prevent broken job definitions from being
            used. This is a keyword-only argument.
        :param validation_kwargs:
            Keyword arguments to pass to the JobDefinition.validate().  Note,
            this is a single argument. This is a keyword-only argument.

        This method simplifies initialization of a Provider1 object where the
        caller already has a Provider1Definition object. Depending on the value
        of ``definition.location`` all of the directories are either None or
        initialized to a *good* (typical) value relative to *location*

        The only value that you may want to adjust, for working with source
        providers, is *locale_dir*, by default it would be ``location/locale``
        but ``manage.py i18n`` creates ``location/build/mo``
        """
        logger.debug("Loading provider from definition %r", definition)
        # Initialize the provider object
        return cls(
            definition.name, definition.namespace or None, definition.version,
            definition.description, secure,
            definition.effective_gettext_domain,
            definition.effective_units_dir, definition.effective_jobs_dir,
            definition.effective_whitelists_dir, definition.effective_data_dir,
            definition.effective_bin_dir, definition.effective_locale_dir,
            definition.location or None, validate=validate,
            validation_kwargs=validation_kwargs, check=check, context=context)

    def __repr__(self):
        return "<{} name:{!r}>".format(self.__class__.__name__, self.name)

    def __str__(self):
        return "{}, version {}".format(self.name, self.version)

    @property
    def name(self):
        """
        name of this provider
        """
        return self._name

    @property
    def namespace(self):
        """
        namespace component of the provider name

        This property defines the namespace in which all provider jobs are
        defined in. Jobs within one namespace do not need to be fully qualified
        by prefixing their partial identifier with provider namespace (so all
        stays 'as-is'). Jobs that need to interact with other provider
        namespaces need to use the fully qualified job identifier instead.

        The identifier is defined as the part of the provider name, up to the
        colon. This effectively gives organizations flat namespace within one
        year-domain pair and allows to create private namespaces by using
        sub-domains.
        """
        return self._namespace

    @property
    def has_dedicated_namespace(self):
        """Flag set if namespace was defined by a dedicated field."""
        return self._has_dedicated_namespace

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

    def tr_description(self):
        """
        Get the translated version of :meth:`description`
        """
        return self.get_translated_data(self.description)

    @property
    def units_dir(self):
        """
        absolute path of the units directory
        """
        return self._units_dir

    @property
    def jobs_dir(self):
        """
        absolute path of the jobs directory
        """
        return self._jobs_dir

    @property
    def whitelists_dir(self):
        """
        absolute path of the whitelist directory
        """
        return self._whitelists_dir

    @property
    def data_dir(self):
        """
        absolute path of the data directory
        """
        return self._data_dir

    @property
    def bin_dir(self):
        """
        absolute path of the bin directory

        .. note::
            The programs in that directory may not work without setting
            PYTHONPATH and CHECKBOX_SHARE.
        """
        return self._bin_dir

    @property
    def locale_dir(self):
        """
        absolute path of the directory with locale data

        The value is applicable as argument bindtextdomain()
        """
        return self._locale_dir

    @property
    def base_dir(self):
        """
        path of the directory with (perhaps) all of jobs_dir, whitelists_dir,
        data_dir, bin_dir, locale_dir. This may be None
        """
        return self._base_dir

    @property
    def build_dir(self):
        """
        absolute path of the build directory

        This value may be None. It depends on location/base_dir being set.
        """
        if self.base_dir is not None:
            return os.path.join(self.base_dir, 'build')

    @property
    def build_bin_dir(self):
        """
        absolute path of the build/bin directory

        This value may be None. It depends on location/base_dir being set.
        """
        if self.base_dir is not None:
            return os.path.join(self.base_dir, 'build', 'bin')

    @property
    def build_mo_dir(self):
        """
        absolute path of the build/mo directory

        This value may be None. It depends on location/base_dir being set.
        """
        if self.base_dir is not None:
            return os.path.join(self.base_dir, 'build', 'mo')

    @property
    def src_dir(self):
        """
        absolute path of the src/ directory

        This value may be None. It depends on location/base_dir set.
        """
        if self.base_dir is not None:
            return os.path.join(self.base_dir, 'src')

    @property
    def po_dir(self):
        """
        absolute path of the po/ directory

        This value may be None. It depends on location/base_dir set.
        """
        if self.base_dir is not None:
            return os.path.join(self.base_dir, 'po')

    @property
    def CHECKBOX_SHARE(self):
        """
        required value of CHECKBOX_SHARE environment variable.

        .. note::
            This variable is only required by one script.
            It would be nice to remove this later on.
        """
        return self.base_dir

    @property
    def extra_PYTHONPATH(self):
        """
        additional entry for PYTHONPATH, if needed.

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

    @property
    def unit_list(self):
        """
        List of loaded units.

        This list may contain units of various types. You should not assume all
        of them are :class:`JobDefinition` instances. You may use filtering to
        obtain units of a given type.

            >>> [unit for unit in provider.unit_list
            ...  if unit.Meta.name == 'job']
            [...]
        """
        self._ensure_loaded()
        return self._loader.unit_list

    @property
    def job_list(self):
        """
        A sorted list of loaded job definition units.
        """
        return sorted(
            (unit for unit in self.unit_list if unit.Meta.name == 'job'),
            key=lambda unit: unit.id)

    @property
    def executable_list(self):
        """
        List of all the executables
        """
        return sorted(
            unit.path for unit in self.unit_list
            if unit.Meta.name == 'file'
            and unit.role in (FileRole.script, FileRole.binary))

    @property
    def whitelist_list(self):
        """
        List of loaded whitelists.

        .. warning::
            :class:`WhiteList` is currently deprecated. You should never need
            to access them in any new code.  They are entirely replaced by
            :class:`TestPlan`. This property is provided for completeness and
            it will be **removed** once whitelists classes are no longer used.
        """
        self._ensure_loaded()
        return self._loader.whitelist_list

    @property
    def problem_list(self):
        """
        list of problems encountered by the loading process
        """
        self._ensure_loaded()
        return self._loader.problem_list

    @property
    def id_map(self):
        """
        A mapping from unit identifier to list of units with that identifier.

        .. note::
            Typically the list will be one element long but invalid providers
            may break that guarantee. Code defensively if you can.
        """
        self._ensure_loaded()
        return self._loader.id_map

    @property
    def path_map(self):
        """
        A mapping from filename path to a list of units stored in that file.

        .. note::
            For ``.pxu`` files this will enumerate all units stored there. For
            other things it will typically be just the FileUnit.
        """
        self._ensure_loaded()
        return self._loader.path_map

    def get_translated_data(self, msgid):
        """
        Get a localized piece of data

        :param msgid:
            data to translate
        :returns:
            translated data obtained from the provider if msgid is not False
            (empty string and None both are) and this provider has a
            gettext_domain defined for it, msgid itself otherwise.
        """
        if msgid and self._gettext_domain:
            return gettext.dgettext(self._gettext_domain, msgid)
        else:
            return msgid

    @property
    def classify(self):
        """
        Exposed :meth:`ProviderContentClassifier.classify()`
        """
        return self._classifier.classify

    @property
    def content_collection(self) -> "IPlugInCollection":
        """
        Exposed :meth:`ProviderContentEnumerator.content_collection`
        """
        return self._enumerator.content_collection

    @property
    def fake(self):
        """
        Bridge to ``.content_collection.fake_plugins`` that's shorter to type.
        """
        return self._enumerator.content_collection.fake_plugins


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
            identifiers separated by dots, at least one dot has to be present
        identifier:
            `[a-z][a-z0-9-]*`
    """

    def __init__(self):
        super(IQNValidator, self).__init__(
            "^[0-9]{4}\.[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+:[a-z][a-z0-9-]*$")

    def __call__(self, variable, new_value):
        if super(IQNValidator, self).__call__(variable, new_value):
            return _("must look like RFC3720 IQN")


class ProviderNameValidator(PatternValidator):

    """
    Validator for the provider name.

    Two forms are allowed:

        - short form (requires a separate namespace definition)
        - verbose form (based on RFC3720 IQN-like strings)

    The short form is supposed to look like Debian package name.
    """

    _PATTERN = (
        "^"
        "([0-9]{4}\.[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+:[a-z][a-z0-9-]*)"
        "|"
        "([a-z0-9-]+)"
        "$"
    )

    def __init__(self):
        super().__init__(self._PATTERN)

    def __call__(self, variable, new_value):
        if super().__call__(variable, new_value):
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

    .. note::

        The location attribute is special, if set, it defines the base
        directory of *all* the other directory attributes. If location is
        unset, then all the directory attributes default to None (that is,
        there is no directory of that type). This is actually a convention that
        is implemented in :class:`Provider1PlugIn`. Here, all the attributes
        can be Unset and their validators only check values other than Unset.
    """


    # NOTE: See the implementation note in :class:`Provider1PluginIn` to
    # understand the effect of this flag.
    relocatable = Variable(
        section='PlainBox Provider',
        help_text=_("Flag indicating if the provider is relocatable"),
        kind=bool,
    )

    location = Variable(
        section='PlainBox Provider',
        help_text=_("Base directory with provider data"),
        validator_list=[
            # NOTE: it *can* be unset!
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
            ProviderNameValidator(),
        ])

    namespace = Variable(
        section='PlainBox Provider',
        help_text=_("Namespace of the provider"),
        validator_list=[
            # NOTE: it *can* be unset, then name must be IQN
            NotEmptyValidator(),
        ])

    @property
    def name_without_colon(self):
        if ':' in self.name:
            return self.name.replace(':', '.')
        else:
            return self.name

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
        help_text=_("Name of the gettext domain for translations"),
        validator_list=[
            # NOTE: it *can* be unset!
            PatternValidator("[a-z0-9_-]+"),
        ])

    @property
    def effective_gettext_domain(self):
        """
        effective value of gettext_domian

        The effective value is :meth:`gettex_domain` itself, unless it is
        Unset. If it is Unset the effective value None.
        """
        if self.gettext_domain is not Unset:
            return self.gettext_domain

    units_dir = Variable(
        section='PlainBox Provider',
        help_text=_("Pathname of the directory with unit definitions"),
        validator_list=[
            # NOTE: it *can* be unset
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    @property
    def implicit_units_dir(self):
        """
        implicit value of units_dir (if Unset)

        The implicit value is only defined if location is not Unset. It is the
        'units' subdirectory of the directory that location points to.
        """
        if self.location is not Unset:
            return os.path.join(self.location, "units")

    @property
    def effective_units_dir(self):
        """
        effective value of units_dir

        The effective value is :meth:`units_dir` itself, unless it is Unset. If
        it is Unset the effective value is the :meth:`implicit_units_dir`, if
        that value would be valid. The effective value may be None.
        """
        if self.units_dir is not Unset:
            return self.units_dir
        implicit = self.implicit_units_dir
        if implicit is not None and os.path.isdir(implicit):
            return implicit

    jobs_dir = Variable(
        section='PlainBox Provider',
        help_text=_("Pathname of the directory with job definitions"),
        validator_list=[
            # NOTE: it *can* be unset
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    @property
    def implicit_jobs_dir(self):
        """
        implicit value of jobs_dir (if Unset)

        The implicit value is only defined if location is not Unset. It is the
        'jobs' subdirectory of the directory that location points to.
        """
        if self.location is not Unset:
            return os.path.join(self.location, "jobs")

    @property
    def effective_jobs_dir(self):
        """
        effective value of jobs_dir

        The effective value is :meth:`jobs_dir` itself, unless it is Unset. If
        it is Unset the effective value is the :meth:`implicit_jobs_dir`, if
        that value would be valid. The effective value may be None.
        """
        if self.jobs_dir is not Unset:
            return self.jobs_dir
        implicit = self.implicit_jobs_dir
        if implicit is not None and os.path.isdir(implicit):
            return implicit

    whitelists_dir = Variable(
        section='PlainBox Provider',
        help_text=_("Pathname of the directory with whitelists definitions"),
        validator_list=[
            # NOTE: it *can* be unset
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    @property
    def implicit_whitelists_dir(self):
        """
        implicit value of whitelists_dir (if Unset)

        The implicit value is only defined if location is not Unset. It is the
        'whitelists' subdirectory of the directory that location points to.
        """
        if self.location is not Unset:
            return os.path.join(self.location, "whitelists")

    @property
    def effective_whitelists_dir(self):
        """
        effective value of whitelists_dir

        The effective value is :meth:`whitelists_dir` itself, unless it is
        Unset. If it is Unset the effective value is the
        :meth:`implicit_whitelists_dir`, if that value would be valid. The
        effective value may be None.
        """
        if self.whitelists_dir is not Unset:
            return self.whitelists_dir
        implicit = self.implicit_whitelists_dir
        if implicit is not None and os.path.isdir(implicit):
            return implicit

    data_dir = Variable(
        section='PlainBox Provider',
        help_text=_("Pathname of the directory with provider data"),
        validator_list=[
            # NOTE: it *can* be unset
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    @property
    def implicit_data_dir(self):
        """
        implicit value of data_dir (if Unset)

        The implicit value is only defined if location is not Unset. It is the
        'data' subdirectory of the directory that location points to.
        """
        if self.location is not Unset:
            return os.path.join(self.location, "data")

    @property
    def effective_data_dir(self):
        """
        effective value of data_dir

        The effective value is :meth:`data_dir` itself, unless it is Unset. If
        it is Unset the effective value is the :meth:`implicit_data_dir`, if
        that value would be valid. The effective value may be None.
        """
        if self.data_dir is not Unset:
            return self.data_dir
        implicit = self.implicit_data_dir
        if implicit is not None and os.path.isdir(implicit):
            return implicit

    bin_dir = Variable(
        section='PlainBox Provider',
        help_text=_("Pathname of the directory with provider executables"),
        validator_list=[
            # NOTE: it *can* be unset
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    @property
    def implicit_bin_dir(self):
        """
        implicit value of bin_dir (if Unset)

        The implicit value is only defined if location is not Unset. It is the
        'bin' subdirectory of the directory that location points to.
        """
        if self.location is not Unset:
            return os.path.join(self.location, "bin")

    @property
    def effective_bin_dir(self):
        """
        effective value of bin_dir

        The effective value is :meth:`bin_dir` itself, unless it is Unset. If
        it is Unset the effective value is the :meth:`implicit_bin_dir`, if
        that value would be valid. The effective value may be None.
        """
        if self.bin_dir is not Unset:
            return self.bin_dir
        implicit = self.implicit_bin_dir
        if implicit is not None and os.path.isdir(implicit):
            return implicit

    locale_dir = Variable(
        section='PlainBox Provider',
        help_text=_("Pathname of the directory with locale data"),
        validator_list=[
            # NOTE: it *can* be unset
            NotEmptyValidator(),
            AbsolutePathValidator(),
            ExistingDirectoryValidator(),
        ])

    @property
    def implicit_locale_dir(self):
        """
        implicit value of locale_dir (if Unset)

        The implicit value is only defined if location is not Unset. It is the
        'locale' subdirectory of the directory that location points to.
        """
        if self.location is not Unset:
            return os.path.join(self.location, "locale")

    @property
    def implicit_build_locale_dir(self):
        """
        implicit value of locale_dir (if Unset) as laid out in the source tree

        This value is only applicable to source layouts, where the built
        translation catalogs are in the build/mo directory.
        """
        if self.location is not Unset:
            return os.path.join(self.location, "build", "mo")

    @property
    def effective_locale_dir(self):
        """
        effective value of locale_dir

        The effective value is :meth:`locale_dir` itself, unless it is Unset.
        If it is Unset the effective value is the :meth:`implicit_locale_dir`,
        if that value would be valid. The effective value may be None.
        """
        if self.locale_dir is not Unset:
            return self.locale_dir
        implicit1 = self.implicit_locale_dir
        if implicit1 is not None and os.path.isdir(implicit1):
            return implicit1
        implicit2 = self.implicit_build_locale_dir
        if implicit2 is not None and os.path.isdir(implicit2):
            return implicit2

    def validate_whole(self):
        """
        Validate the provider definition object.

        :raises ValidationError:
            If the namespace is not defined and name is using a simplified
            format that doesn't contain an embedded namespace part.
        """
        super().validate_whole()
        if not self.namespace:
            variable = self.__class__.name
            value = self.name
            validator = IQNValidator()
            message = validator(variable, value)
            if message is not None:
                raise ConfigValidationError(variable, value, message)


class Provider1PlugIn(PlugIn):
    """
    A specialized IPlugIn that loads Provider1 instances from their definition
    files
    """

    def __init__(self, filename, definition_text, load_time, *, validate=None,
                 validation_kwargs=None, check=None, context=None):
        """
        Initialize the plug-in with the specified name and external object
        """
        start = now()
        self._load_time = load_time
        definition = Provider1Definition()
        # Load the provider definition
        definition.read_string(definition_text)
        # If the relocatable flag is set, set location to the base directory of
        # the filename and reset all the other directories (to Unset). This is
        # to allow creation of .provider files that can be moved entirely, and
        # as long as they follow the implicit source layout, they will work
        # okay.
        if definition.relocatable:
            definition.location = os.path.dirname(filename)
            definition.units_dir = Unset
            definition.jobs_dir = Unset
            definition.whitelists_dir = Unset
            definition.data_dir = Unset
            definition.bin_dir = Unset
            definition.locale_dir = Unset
        # any validation issues prevent plugin from being used
        if definition.problem_list:
            # take the earliest problem and report it
            exc = definition.problem_list[0]
            raise PlugInError(
                _("Problem in provider definition, field {!a}: {}").format(
                    exc.variable.name, exc.message))
        # Get the secure flag
        secure = os.path.dirname(filename) in get_secure_PROVIDERPATH_list()
        # Initialize the provider object
        provider = Provider1.from_definition(
            definition, secure, validate=validate,
            validation_kwargs=validation_kwargs, check=check, context=context)
        wrap_time = now() - start
        super().__init__(provider.name, provider, load_time, wrap_time)

    def __repr__(self):
        return "<{!s} plugin_name:{!r}>".format(
            type(self).__name__, self.plugin_name)


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

    def __init__(self, **kwargs):
        dir_list = get_secure_PROVIDERPATH_list()
        super().__init__(dir_list, '.provider', wrapper=Provider1PlugIn,
                         **kwargs)


# Collection of all providers
all_providers = SecureProvider1PlugInCollection()
