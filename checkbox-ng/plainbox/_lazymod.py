# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

""" Implementation of a lazy module.  """

import inspect
import sys
import types


class LazyModule(types.ModuleType):

    """
    A module subclass that imports things lazily on demand.

    There are some special provisions to make dir() and __all__ work better so
    that pydoc is more informative.

    :ivar _lazy:
        A mapping of 'name' to 'callable'. The callable is called only once and
        defines the lazily loaded version of 'name'.
    :ivar _all:
        A set of all the "public" objects. This is exposed as the module's
        __all__ property. It automatically collects all the objects reported
        via :meth:`lazily()` and :meth:`immediate()`.
    :ivar _old:
        Reference to the old (original) module. This is kept around for python
        2.x compatibility. It also seems to help with implementing __dir__()
    """

    def __init__(self, name, doc, old):
        """ Initialize a new lazy module. """
        super(LazyModule, self).__init__(name, doc)
        self._lazy = {}
        self._all = set()
        self._old = old

    def __dir__(self):
        """ Lazy-aware version of dir().  """
        if sys.version_info[0] == 3:
            data = super(LazyModule, self).__dir__()
        else:
            data = self.__dict__.keys()
        data = set(data) | self._all
        return sorted(data)

    def __getattr__(self, name):
        """ Lazy-aware version of getattr().  """
        try:
            callable, args = self._lazy[name]
        except KeyError:
            raise AttributeError(name)
        value = callable(*args)
        del self._lazy[name]
        setattr(self, name, value)
        return value

    @classmethod
    def shadow_normal_module(cls, mod_name=None):
        """
        Shadow a module with an instance of LazyModule.

        :param mod_name:
            Name of the module to shadow. By default this is the module that is
            making the call into this method. This is not hard-coded as that
            module might be called '__main__' if it is executed via 'python -m'
        :returns:
            A fresh instance of :class:`LazyModule`.
        """
        if mod_name is None:
            frame = inspect.currentframe()
            try:
                mod_name = frame.f_back.f_locals['__name__']
            finally:
                del frame
        orig_mod = sys.modules[mod_name]
        lazy_mod = cls(orig_mod.__name__, orig_mod.__doc__, orig_mod)
        for attr in dir(orig_mod):
            setattr(lazy_mod, attr, getattr(orig_mod, attr))
        sys.modules[mod_name] = lazy_mod
        return lazy_mod

    def lazily(self, name, callable, args):
        """ Load something lazily.  """
        self._lazy[name] = callable, args
        self._all.add(name)

    def immediate(self, name, value):
        """ Load something immediately.  """
        setattr(self, name, value)
        self._all.add(name)

    @property
    def __all__(self):
        """
        A lazy-aware version of __all__.

        In addition to exposing all of the original module's __all__ it also
        contains all the (perhaps not yet loaded) objects defined via
        :meth:`lazily()`
        """
        return sorted(self._all)

    @__all__.setter
    def __all__(self, value):
        """
        Setter for __all__ that just updates the internal set :ivar:`_all`.

        This is used by :meth:`shadow_normal_module()` which copies (assigns)
        all of the original module's attributes, which also assigns __all__.
        """
        self._all.update(value)


def far(import_path):
    """ Helper for lazy imports for :meth:`LazyModule.lazily()`. """
    module_name, func_name = import_path.split(":", 1)
    module = __import__(module_name, fromlist=[''])
    try:
        return getattr(module, func_name)
    except AttributeError:
        raise NotImplementedError(
            "%s.%s does not exist" % (module_name, func_name))
