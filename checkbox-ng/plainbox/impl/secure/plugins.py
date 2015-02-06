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
:mod:`plainbox.impl.secure.plugins` -- interface for accessing extension points
===============================================================================

This module contains plugin interface for plainbox. Plugins are based on
pkg_resources entry points feature. Any python package can advertise the
existence of entry points associated with a given namespace. Any other
package can query a given namespace and enumerate a sequence of entry points.

Each entry point has a name and importable identifier. The identifier can
be imported using the load() method. A loaded entry point is exposed as an
instance of :class:`PlugIn`. A high-level collection of plugins (that may
eventually also query alternate backends) is offered by
:class:`PlugInCollection`.

Using :meth:`PlugInCollection.load()` one can load all plugins from
a particular namespace and work with them using provided utility methods
such as :meth:`PlugInCollection.get_by_name()` or
:meth:`PlugInCollection.get_all_names()`

The set of loaded plugins can be overridden by mock/patching
:meth:`PlugInCollection._get_entry_points()`. This is especially useful for
testing in isolation from whatever entry points may exist in the system.
"""

import abc
import collections
import contextlib
import logging
import os
import time

import pkg_resources

from plainbox.i18n import gettext as _


logger = logging.getLogger("plainbox.secure.plugins")


def now() -> float:
    """
    Get the current "time".

    :returns:
        A fractional number of seconds since some undefined base event.

    This methods returns the current "time" that is useful for measuring
    plug-in loading time. The return value is meaningless but delta between
    two values is a fractional number of seconds between the two
    corresponding events.
    """
    try:
        # time.perf_counter is only available since python 3.3
        return time.perf_counter()
    except AttributeError:
        return time.clock()


class IPlugIn(metaclass=abc.ABCMeta):
    """
    Piece of code loaded at runtime, one of many for a given extension point
    """

    @abc.abstractproperty
    def plugin_name(self) -> str:
        """
        name of the plugin, may not be unique
        """

    @abc.abstractproperty
    def plugin_object(self) -> object:
        """
        external object
        """

    @abc.abstractproperty
    def plugin_load_time(self) -> float:
        """
        time, in fractional seconds, that was needed to load the plugin
        """

    @abc.abstractproperty
    def plugin_wrap_time(self) -> float:
        """
        time, in fractional seconds, that was needed to wrap the plugin

        .. note::
            The difference between ``plugin_wrap_time`` and
            ``plugin_load_time`` depends on context. In practical terms the sum
            of the two is interesting for analysis but in some cases having
            access to both may be important.
        """


class PlugInError(Exception):
    """
    Exception that may be raised by PlugIn.__init__() to signal it cannot
    be fully loaded and should not be added to any collection.
    """


class PlugIn(IPlugIn):
    """
    Simple plug-in that does not offer any guarantees beyond knowing it's name
    and some arbitrary external object.
    """

    def __init__(self, name: str, obj: object, load_time: float=0, wrap_time: float=0):
        """
        Initialize the plug-in with the specified name and external object

        :param name:
            Name of the plug-in object, semantics is application-defined
        :param obj:
            The plugged in object itself
        :param load_time:
            Time it took to load the object (in fractional seconds)
        :param wrap_time:
            Time it took to wrap the object (in fractional seconds)
        """
        self._name = name
        self._obj = obj
        self._load_time = load_time
        self._wrap_time = wrap_time

    def __repr__(self):
        return "<{!s} plugin_name:{!r}>".format(
            type(self).__name__, self.plugin_name)

    @property
    def plugin_name(self) -> str:
        """
        plugin name, arbitrary string
        """
        return self._name

    @property
    def plugin_object(self) -> float:
        """
        plugin object, arbitrary object
        """
        return self._obj

    @property
    def plugin_load_time(self) -> float:
        """
        time, in fractional seconds, that was needed to load the plugin
        """
        return self._load_time

    @property
    def plugin_wrap_time(self) -> float:
        """
        time, in fractional seconds, that was needed to wrap the plugin
        """
        return self._wrap_time


class IPlugInCollection(metaclass=abc.ABCMeta):
    """
    A collection of IPlugIn objects.
    """

    @abc.abstractmethod
    def get_by_name(self, name):
        """
        Get the specified plug-in (by name)
        """

    @abc.abstractmethod
    def get_all_names(self):
        """
        Get an iterator to a sequence of plug-in names
        """

    @abc.abstractmethod
    def get_all_plugins(self):
        """
        Get an iterator to a sequence plug-ins
        """

    @abc.abstractmethod
    def get_all_plugin_objects(self):
        """
        Get an list of plug-in objects

        This is a shortcut that gives fastest access to a list of
        :attr:`IPlugIn.plugin_object` of each loaded plugin.
        """

    @abc.abstractmethod
    def get_all_items(self):
        """
        Get an iterator to a sequence of (name, plug-in)
        """

    @abc.abstractproperty
    def problem_list(self):
        """
        List of problems encountered while loading plugins
        """

    @abc.abstractmethod
    def load(self):
        """
        Load all plug-ins.

        This method loads all plug-ins from the specified name-space.  It may
        perform a lot of IO so it's somewhat slow / expensive on a cold disk
        cache.
        """

    @abc.abstractmethod
    @contextlib.contextmanager
    def fake_plugins(self, plugins, problem_list=None):
        """
        Context manager for using fake list of plugins

        :param plugins:
            list of PlugIn-alike objects
        :param problem_list:
            list of problems (exceptions)

        The provided list of plugins and exceptions overrides any previously
        loaded plugins and prevent loading any other, real, plugins. After the
        context manager exits the previous state is restored.
        """

    @abc.abstractproperty
    def discovery_time(self) -> float:
        """
        Time, in fractional seconds, that was used to discover all objects.

        This time is separate from the load and wrap time of all each
        individual plug-in. Typically this is either a fixed cost or a
        predictable cost related to traversing the file system.
        """

    @abc.abstractmethod
    def get_total_time(self) -> float:
        """
        Get the cost to prepare everything required by this collection

        :returns:
            The total number of fractional seconds of wall-clock time spent on
            discovering, loading and wrapping each object now contained in this
            collection.
        """


class PlugInCollectionBase(IPlugInCollection):
    """
    Base class that shares some of the implementation with the other
    PlugInCollection implemenetations.
    """

    def __init__(self, load=False, wrapper=PlugIn, *wrapper_args,
                 **wrapper_kwargs):
        """
        Initialize a collection of plug-ins

        :param load:
            if true, load all of the plug-ins now
        :param wrapper:
            wrapper class for all loaded objects, defaults to :class:`PlugIn`
        :param wrapper_args:
            additional arguments passed to each instantiated wrapper
        :param wrapper_kwargs:
            additional keyword arguments passed to each instantiated wrapper
        """
        self._wrapper = wrapper
        self._wrapper_args = wrapper_args
        self._wrapper_kwargs = wrapper_kwargs
        self._plugins = collections.OrderedDict()  # str -> IPlugIn instance
        self._loaded = False
        self._problem_list = []
        self._discovery_time = 0
        if load:
            self.load()

    def get_by_name(self, name):
        """
        Get the specified plug-in (by name)

        :param name:
            name of the plugin to locate
        :returns:
            :class:`PlugIn` like object associated with the name
        :raises KeyError:
            if the specified name cannot be found
        """
        return self._plugins[name]

    def get_all_names(self):
        """
        Get a list of all the plug-in names

        :returns:
            a list of plugin names
        """
        return list(self._plugins.keys())

    def get_all_plugins(self):
        """
        Get a list of all the plug-ins

        :returns:
            a list of plugin objects
        """
        return list(self._plugins.values())

    def get_all_plugin_objects(self):
        """
        Get an list of plug-in objects
        """
        return [plugin.plugin_object for plugin in self._plugins.values()]

    def get_all_items(self):
        """
        Get a list of all the pairs of plugin name and plugin

        :returns:
            a list of tuples (plugin.plugin_name, plugin)
        """
        return list(self._plugins.items())

    @property
    def problem_list(self):
        """
        List of problems encountered while loading plugins
        """
        return self._problem_list

    @contextlib.contextmanager
    def fake_plugins(self, plugins, problem_list=None):
        """
        Context manager for using fake list of plugins

        :param plugins:
            list of PlugIn-alike objects
        :param problem_list:
            list of problems (exceptions)

        The provided list of plugins overrides any previously loaded
        plugins and prevent loading any other, real, plugins. After
        the context manager exits the previous state is restored.
        """
        old_loaded = self._loaded
        old_problem_list = self._problem_list
        old_plugins = self._plugins
        self._loaded = True
        self._plugins = collections.OrderedDict([
            (plugin.plugin_name, plugin)
            for plugin in plugins
        ])
        if problem_list is None:
            problem_list = []
        self._problem_list = problem_list
        try:
            yield
        finally:
            self._loaded = old_loaded
            self._plugins = old_plugins
            self._problem_list = old_problem_list

    def wrap_and_add_plugin(self, plugin_name, plugin_obj, plugin_load_time):
        """
        Internal method of PlugInCollectionBase.

        :param plugin_name:
            plugin name, some arbitrary string
        :param plugin_obj:
            plugin object, some arbitrary object.
        :param plugin_load_time:
            number of seconds it took to load this plugin

        This method prepares a wrapper (PlugIn subclass instance) for the
        specified plugin name/object by attempting to instantiate the wrapper
        class. If a PlugInError exception is raised then it is added to the
        problem_list and the corresponding plugin is not added to the
        collection of plugins.
        """
        try:
            wrapper = self._wrapper(
                plugin_name, plugin_obj, plugin_load_time,
                *self._wrapper_args, **self._wrapper_kwargs)
        except PlugInError as exc:
            logger.warning(
                _("Unable to prepare plugin %s: %s"), plugin_name, exc)
            self._problem_list.append(exc)
        else:
            self._plugins[plugin_name] = wrapper

    @property
    def discovery_time(self) -> float:
        """
        Time, in fractional seconds, that was required to discover all objects.

        This time is separate from the load and wrap time of all each
        individual plug-in. Typically this is either a fixed cost or a
        predictable cost related to traversing the file system.
        """
        if self._loaded is False:
            raise AttributeError(
                _("discovery_time is meaningful after calling load()"))
        return self._discovery_time

    def get_total_time(self) -> float:
        """
        Get the sum of load and wrap time of each plugin object

        :returns:
            The total number of fractional seconds of wall-clock time spent by
            loading this collection. This value doesn't include some small
            overhead of this class but is representative of the load times of
            pluggable code.
        """
        return sum(
            plugin.plugin_load_time + plugin.plugin_wrap_time
            for plugin in self._plugins.values()) + self.discovery_time


class PkgResourcesPlugInCollection(PlugInCollectionBase):
    """
    Collection of plug-ins based on pkg_resources

    Instantiate with :attr:`namespace`, call :meth:`load()` and then access any
    of the loaded plug-ins using the API offered. All loaded objects are
    wrapped by a plug-in container. By default that is :class:`PlugIn` but it
    may be adjusted if required.
    """

    def __init__(self, namespace, load=False, wrapper=PlugIn, *wrapper_args,
                 **wrapper_kwargs):
        """
        Initialize a collection of plug-ins from the specified name-space.

        :param namespace:
            pkg_resources entry-point name-space of the plug-in collection
        :param load:
            if true, load all of the plug-ins now
        :param wrapper:
            wrapper class for all loaded objects, defaults to :class:`PlugIn`
        :param wrapper_args:
            additional arguments passed to each instantiated wrapper
        :param wrapper_kwargs:
            additional keyword arguments passed to each instantiated wrapper
        """
        self._namespace = namespace
        super().__init__(load, wrapper, *wrapper_args, **wrapper_kwargs)

    def load(self):
        """
        Load all plug-ins.

        This method loads all plug-ins from the specified name-space.  It may
        perform a lot of IO so it's somewhat slow / expensive on a cold disk
        cache.

        .. note::
            this method queries pkg-resources only once.
        """
        if self._loaded:
            return
        self._loaded = True
        start_time = now()
        entry_point_list = list(self._get_entry_points())
        entry_point_list.sort(key=lambda ep: ep.name)
        self._discovery_time = now() - start_time
        for entry_point in entry_point_list:
            start_time = now()
            try:
                obj = entry_point.load()
            except ImportError as exc:
                logger.exception(_("Unable to import %s"), entry_point)
                self._problem_list.append(exc)
            else:
                self.wrap_and_add_plugin(
                    entry_point.name, obj, now() - start_time)

    def _get_entry_points(self):
        """
        Get entry points from pkg_resources.

        This is the method you want to mock if you are writing unit tests
        """
        return pkg_resources.iter_entry_points(self._namespace)


class FsPlugInCollection(PlugInCollectionBase):
    """
    Collection of plug-ins based on filesystem entries

    Instantiate with :attr:`dir_list` and :attr:`ext`, call :meth:`load()` and
    then access any of the loaded plug-ins using the API offered. All loaded
    plugin information files are wrapped by a plug-in container. By default
    that is :class:`PlugIn` but it may be adjusted if required.

    The name of each plugin is the base name of the plugin file, the object of
    each plugin is the text read from the plugin file.
    """

    def __init__(self, dir_list, ext, recursive=False, load=False,
                 wrapper=PlugIn, *wrapper_args, **wrapper_kwargs):
        """
        Initialize a collection of plug-ins from the specified name-space.

        :param dir_list:
            a list of directories to search
        :param ext:
            extension of each plugin definition file (or a list of those)
        :param recursive:
            a flag that indicates if we should perform recursive search
            (default False)
        :param load:
            if true, load all of the plug-ins now
        :param wrapper:
            wrapper class for all loaded objects, defaults to :class:`PlugIn`
        :param wrapper_args:
            additional arguments passed to each instantiated wrapper
        :param wrapper_kwargs:
            additional keyword arguments passed to each instantiated wrapper
        """
        if (not isinstance(dir_list, list)
                or not all(isinstance(item, str) for item in dir_list)):
            raise TypeError("dir_list needs to be List[str]")
        self._dir_list = dir_list
        self._ext = ext
        self._recursive = recursive
        super().__init__(load, wrapper, *wrapper_args, **wrapper_kwargs)

    def load(self):
        """
        Load all plug-ins.

        This method loads all plug-ins from the search directories (as defined
        by the path attribute). Missing directories are silently ignored.
        """
        if self._loaded:
            return
        self._loaded = True
        start_time = now()
        filename_list = list(self._get_plugin_files())
        filename_list.sort()
        self._discovery_time = now() - start_time
        for filename in filename_list:
            start_time = now()
            try:
                text = self._get_file_text(filename)
            except (OSError, IOError) as exc:
                logger.error(_("Unable to load %r: %s"), filename, str(exc))
                self._problem_list.append(exc)
            else:
                self.wrap_and_add_plugin(filename, text, now() - start_time)

    def _get_file_text(self, filename):
        with open(filename, encoding='UTF-8') as stream:
            return stream.read()

    def _get_plugin_files(self):
        """
        Enumerate (generate) all plugin files according to 'path' and 'ext'
        """
        # Look in all parts of 'path' separated by standard system path
        # separator.
        for dirname in self._dir_list:
            if self._recursive:
                entries = []
                for base_dir, dirs, files in os.walk(dirname):
                    entries.extend([
                        os.path.relpath(
                            os.path.join(base_dir, filename), dirname)
                        for filename in files])
            else:
                # List all files in each path component
                try:
                    entries = os.listdir(dirname)
                except OSError:
                    # Silently ignore anything we cannot access
                    continue
            # Look at each file there
            for entry in entries:
                # Skip files with other extensions
                if isinstance(self._ext, str):
                    if not entry.endswith(self._ext):
                        continue
                elif isinstance(self._ext, collections.Sequence):
                    for ext in self._ext:
                        if entry.endswith(ext):
                            break
                    else:
                        continue
                info_file = os.path.join(dirname, entry)
                # Skip all non-files
                if not os.path.isfile(info_file):
                    continue
                yield info_file


class LazyFileContent:
    """
    Support class for FsPlugInCollection's subclasses that behaves like a
    string of text loaded from a file. The actual text is loaded on demand, the
    first time it is needed.

    The actual methods implemented here are just enough to work for loading a
    provider. Since __getattr__() is implemented the class should be pretty
    versatile but your millage may vary.
    """

    def __init__(self, name):
        self.name = name
        self._text = None

    def __repr__(self):
        return "<{} name:{!r}{}>".format(
            self.__class__.__name__, self.name,
            ' (pending)' if self._text is None else ' (loaded)')

    def __str__(self):
        self._ensure_loaded()
        return self._text

    def __iter__(self):
        self._ensure_loaded()
        return iter(self._text.splitlines(True))

    def __getattr__(self, attr):
        self._ensure_loaded()
        return getattr(self._text, attr)

    def _ensure_loaded(self):
        if self._text is None:
            with open(self.name, encoding='UTF-8') as stream:
                self._text = stream.read()


class LazyFsPlugInCollection(FsPlugInCollection):
    """
    Collection of plug-ins based on filesystem entries

    Instantiate with :attr:`dir_list` and :attr:`ext`, call :meth:`load()` and
    then access any of the loaded plug-ins using the API offered. All loaded
    plugin information files are wrapped by a plug-in container. By default
    that is :class:`PlugIn` but it may be adjusted if required.

    The name of each plugin is the base name of the plugin file, the object of
    each plugin is a handle that can be used to optionally load the content of
    the file.
    """

    def _get_file_text(self, filename):
        return LazyFileContent(filename)


class LazyPlugInCollection(PlugInCollectionBase):
    """
    Collection of plug-ins based on a mapping of imported objects

    All loaded plugin information files are wrapped by a plug-in container. By
    default that is :class:`PlugIn` but it may be adjusted if required.
    """

    def __init__(self, mapping, load=False, wrapper=PlugIn,
                 *wrapper_args, **wrapper_kwargs):
        """
        Initialize a collection of plug-ins from the specified mapping of
        callbacks.

        :param callback_args_map:
            any mapping from from any string (the plugin name) to a tuple
            ("module:obj", *args) that if imported and called ``obj(*args)``
            produces the plugin object, alternatively, a mapping from the same
            string to a string that is imported but *not* called.
        :param load:
            if true, load all of the plug-ins now
        :param wrapper:
            wrapper class for all loaded objects, defaults to :class:`PlugIn`
        :param wrapper_args:
            additional arguments passed to each instantiated wrapper
        :param wrapper_kwargs:
            additional keyword arguments passed to each instantiated wrapper
        """
        self._mapping = mapping
        super().__init__(load, wrapper, *wrapper_args, **wrapper_kwargs)

    def load(self):
        if self._loaded:
            return
        logger.debug(_("Loading everything in %r"), self)
        self._loaded = True
        name_discovery_data_list = self.discover()
        for name, discovery_data in name_discovery_data_list:
            if name in self._plugins:
                continue
            self.load_one(name, discovery_data)

    def discover(self):
        start = now()
        result = self.do_discover()
        self._discovery_time = now() - start
        return result

    def load_one(self, name, discovery_data):
        start_time = now()
        try:
            logger.debug(_("Loading %r"), name)
            obj = self.do_load_one(name, discovery_data)
        except (ImportError, AttributeError, ValueError) as exc:
            logger.exception(_("Unable to load: %r"), name)
            self._problem_list.append(exc)
        else:
            logger.debug(_("Wrapping %r"), name)
            self.wrap_and_add_plugin(name, obj, now() - start_time)

    def do_discover(self):
        return self._mapping.items()

    def do_load_one(self, name, discovery_data):
        if isinstance(discovery_data, tuple):
            callable_obj = discovery_data[0]
            args = discovery_data[1:]
        else:
            callable_obj = discovery_data
            args = None
        if isinstance(callable_obj, str):
            logger.debug(_("Importing %s"),  callable_obj)
            callable_obj = getattr(
                __import__(
                    callable_obj.split(':', 1)[0], fromlist=[1]),
                callable_obj.split(':', 1)[1])
        logger.debug(_("Calling %r with %r"), callable_obj, args)
        if args is None:
            return callable_obj
        else:
            return callable_obj(*args)

    def get_all_names(self):
        """
        Get a list of all the plug-in names

        :returns:
            a list of plugin names
        """
        if self._loaded:
            return super().get_all_names()
        else:
            return list(self._mapping.keys())

    def get_by_name(self, name):
        """
        Get the specified plug-in (by name)

        :param name:
            name of the plugin to locate
        :returns:
            :class:`PlugIn` like object associated with the name
        :raises KeyError:
            if the specified name cannot be found
        """
        if self._loaded:
            return super().get_by_name(name)
        if name not in self._plugins:
            discovery_data = self._mapping[name]
            self.load_one(name, discovery_data)
        return self._plugins[name]

    @property
    def discovery_time(self) -> float:
        """
        Time, in fractional seconds, that was required to discover all objects.

        This time is separate from the load and wrap time of all each
        individual plug-in. Typically this is either a fixed cost or a
        predictable cost related to traversing the file system.

        .. note::
            This overridden version can be called at any time, unlike the base
            class implementation. Before all discovery is done, it simply
            returns zero.
        """
        return self._discovery_time

    @contextlib.contextmanager
    def fake_plugins(self, plugins, problem_list=None):
        old_mapping = self._mapping
        self._mapping = {}  # fake the mapping
        try:
            with super().fake_plugins(plugins, problem_list):
                yield
        finally:
            self._mapping = old_mapping
