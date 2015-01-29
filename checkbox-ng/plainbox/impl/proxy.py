# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
:mod:`plainbox.impl.proxy ` -- mostly transparent proxy
=======================================================

.. note::
    There are a number of classes and meta-classes but the only public
    interface is the :class:`proxy` class. See below for examples.
"""
import logging
import itertools

_logger = logging.getLogger("plainbox.proxy")


__all__ = ['proxy']


class proxy_meta(type):
    """
    Meta-class for all proxy types

    This meta-class is responsible for gathering the __unproxied__ attribute on
    each created class. The attribute is a frosenset of names that will not be
    forwarded to the ``proxxie`` but instead will be looked up on the proxy
    itself.
    """

    def __new__(mcls, name, bases, ns):
        _logger.debug(
            "__new__ on proxy_meta with name: %r, bases: %r", name, bases)
        unproxied_set = set()
        for base in bases:
            if hasattr(base, '__unproxied__'):
                unproxied_set.update(base.__unproxied__)
        for ns_attr, ns_value in ns.items():
            if getattr(ns_value, 'unproxied', False):
                unproxied_set.add(ns_attr)
        if unproxied_set:
            _logger.debug(
                "proxy type %r will pass-thru %r", name, unproxied_set)
        ns['__unproxied__'] = frozenset(unproxied_set)
        return super().__new__(mcls, name, bases, ns)


cnt = itertools.count()


def make_boundproxy_meta(proxiee):
    """
    Make a new bound proxy meta-class for the specified object

    :param proxiee:
        The object that will be proxied
    :returns:
        A new meta-class that lexically wraps ``proxiee`` and subclasses
        :class:`proxy_meta`.
    """

    class boundproxy_meta(proxy_meta):
        """
        Meta-class for all bound proxies.

        This meta-class is responsible for generating an unique name for each
        created class and setting the setting the ``__proxiee__`` attribute to
        the proxiee object itself.

        In addition, it implements two methods that participate in instance and
        class checks: ``__instancecheck__`` and ``__subclasscheck__``.
        """

        def __new__(mcls, name, bases, ns):
            name = 'boundproxy[{!r}]'.format(next(cnt))
            _logger.debug(
                "__new__ on boundproxy_meta with name %r and bases %r",
                name, bases)
            ns['__proxiee__'] = proxiee
            return super().__new__(mcls, name, bases, ns)

        def __instancecheck__(mcls, instance):
            # NOTE: this is never called in practice since
            # proxy(obj).__class__ is really obj.__class__.
            _logger.debug("__instancecheck__ %r on %r", instance, proxiee)
            return isinstance(instance, type(proxiee))

        def __subclasscheck__(mcls, subclass):
            # This is still called though since type(proxy(obj)) is
            # something else
            _logger.debug("__subclasscheck__ %r on %r", subclass, proxiee)
            return issubclass(type(proxiee), subclass)

    return boundproxy_meta


class proxy_base:
    """
    Base class for all proxies.

    This class implements the bulk of the proxy work by having a lot of dunder
    methods that delegate their work to a ``proxiee`` object. The ``proxiee``
    object must be available as the ``__proxiee__`` attribute on a class
    deriving from ``base_proxy``. Apart from ``__proxiee__`, the
    ``__unproxied__`` attribute, which should be a frozenset, must also be
    present in all derived classes.

    In practice, the two special attributes are injected via
    ``boundproxy_meta`` created by :func:`make_boundproxy_meta()`. This class
    is also used as a base class for the tricky :class:`proxy` below.

    NOTE: Look at ``pydoc3 SPECIALMETHODS`` section titled ``Special method
    lookup`` for a rationale of why we have all those dunder methods while
    still having __getattribute__()
    """
    # NOTE: the order of methods below matches that of ``pydoc3
    # SPECIALMETHODS``. The "N/A to instances" text means that it makes no
    # sense to add proxy support to the specified method because that method
    # makes no sense on instances. Proxy is designed to intercept access to
    # *objects*, not construction of such objects in the first place.

    # N/A to instances: __new__

    # N/A to instances: __init__

    def __del__(self):
        """
        NOTE: this method is handled specially since it must be called
        after an object becomes unreachable. As long as the proxy object
        itself exits, it holds a strong reference to the original object.
        """

    def __repr__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__repr__ on proxiee (%r)", proxiee)
        return repr(proxiee)

    def __str__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__str__ on proxiee (%r)", proxiee)
        return str(proxiee)

    def __bytes__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__bytes__ on proxiee (%r)", proxiee)
        return bytes(proxiee)

    def __format__(self, format_spec):
        proxiee = type(self).__proxiee__
        _logger.debug("__format__ on proxiee (%r)", proxiee)
        return format(proxiee, format_spec)

    def __lt__(self, other):
        proxiee = type(self).__proxiee__
        _logger.debug("__lt__ on proxiee (%r)", proxiee)
        return proxiee < other

    def __le__(self, other):
        proxiee = type(self).__proxiee__
        _logger.debug("__le__ on proxiee (%r)", proxiee)
        return proxiee <= other

    def __eq__(self, other):
        proxiee = type(self).__proxiee__
        _logger.debug("__eq__ on proxiee (%r)", proxiee)
        return proxiee == other

    def __ne__(self, other):
        proxiee = type(self).__proxiee__
        _logger.debug("__ne__ on proxiee (%r)", proxiee)
        return proxiee != other

    def __gt__(self, other):
        proxiee = type(self).__proxiee__
        _logger.debug("__gt__ on proxiee (%r)", proxiee)
        return proxiee > other

    def __ge__(self, other):
        proxiee = type(self).__proxiee__
        _logger.debug("__ge__ on proxiee (%r)", proxiee)
        return proxiee >= other

    def __hash__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__hash__ on proxiee (%r)", proxiee)
        return hash(proxiee)

    def __bool__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__bool__ on proxiee (%r)", proxiee)
        return bool(proxiee)

    def __getattr__(self, name):
        proxiee = type(self).__proxiee__
        _logger.debug("__getattr__ %r on proxiee (%r)", name, proxiee)
        return getattr(proxiee, name)

    def __getattribute__(self, name):
        cls = type(self)
        if name not in cls.__unproxied__:
            proxiee = cls.__proxiee__
            _logger.debug("__getattribute__ %r on proxiee (%r)", name, proxiee)
            return getattr(proxiee, name)
        else:
            _logger.debug("__getattribute__ %r on proxy itself", name)
            return object.__getattribute__(self, name)

    def __setattr__(self, attr, value):
        proxiee = type(self).__proxiee__
        _logger.debug("__setattr__ %r on proxiee (%r)", attr, proxiee)
        setattr(proxiee, attr, value)

    def __delattr__(self, attr):
        proxiee = type(self).__proxiee__
        _logger.debug("__delattr__ %r on proxiee (%r)", attr, proxiee)
        delattr(proxiee, attr)

    def __dir__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__dir__ on proxiee (%r)", proxiee)
        return dir(proxiee)

    def __get__(self, instance, owner):
        proxiee = type(self).__proxiee__
        _logger.debug("__get__ on proxiee (%r)", proxiee)
        return proxiee.__get__(instance, owner)

    def __set__(self, instance, value):
        proxiee = type(self).__proxiee__
        _logger.debug("__set__ on proxiee (%r)", proxiee)
        proxiee.__set__(instance, value)

    def __delete__(self, instance):
        proxiee = type(self).__proxiee__
        _logger.debug("__delete__ on proxiee (%r)", proxiee)
        proxiee.__delete__(instance)

    def __call__(self, *args, **kwargs):
        proxiee = type(self).__proxiee__
        _logger.debug("call on proxiee (%r)", proxiee)
        return proxiee(*args, **kwargs)

    def __len__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__len__ on proxiee (%r)", proxiee)
        return len(proxiee)

    def __length_hint__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__length_hint__ on proxiee (%r)", proxiee)
        return proxiee.__length_hint__()

    def __getitem__(self, item):
        proxiee = type(self).__proxiee__
        _logger.debug("__getitem__ on proxiee (%r)", proxiee)
        return proxiee[item]

    def __setitem__(self, item, value):
        proxiee = type(self).__proxiee__
        _logger.debug("__setitem__ on proxiee (%r)", proxiee)
        proxiee[item] = value

    def __delitem__(self, item):
        proxiee = type(self).__proxiee__
        _logger.debug("__delitem__ on proxiee (%r)", proxiee)
        del proxiee[item]

    def __iter__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__iter__ on proxiee (%r)", proxiee)
        return iter(proxiee)

    def __reversed__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__reversed__ on proxiee (%r)", proxiee)
        return reversed(proxiee)

    def __contains__(self, item):
        proxiee = type(self).__proxiee__
        _logger.debug("__contains__ on proxiee (%r)", proxiee)
        return item in proxiee

    # TODO: all numeric methods

    def __enter__(self):
        proxiee = type(self).__proxiee__
        _logger.debug("__enter__ on proxiee (%r)", proxiee)
        return proxiee.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        proxiee = type(self).__proxiee__
        _logger.debug("__exit__ on proxiee (%r)", proxiee)
        return proxiee.__exit__(exc_type, exc_value, traceback)


class proxy(proxy_base, metaclass=proxy_meta):
    """
    A mostly transparent proxy type

    The proxy class can be used in two different ways. First, as a callable
    ``proxy(obj)``. This simply returns a proxy for a single object.

        >>> truth = ['trust no one']
        >>> lie = proxy(truth)

    This will return an instance of a new ``proxy`` sub-class which for all
    intents and purposes, to the extent possible in CPython, forwards all
    requests to the original object.

    One can still examine the proxy with some ways::

        >>> lie is truth
        False
        >>> type(lie) is type(truth)
        False

    Having said that, the vast majority of stuff will make the proxy behave
    identically to the original object.

        >>> lie[0]
        'trust no one'
        >>> lie[0] = 'trust the government'
        >>> truth[0]
        'trust the government'

    The second way of using the ``proxy`` class is as a base class. In this
    way, one can actually override certain methods. To ensure that all the
    dunder methods work correctly please use the ``@unproxied`` decorator on
    them.

        >>> import codecs
        >>> class crypto(proxy):
        ...
        ...     @unproxied
        ...     def __repr__(self):
        ...         return codecs.encode(super().__repr__(), "rot_13")

    With this weird class, we can change the repr() of any object we want to be
    ROT-13 encoded. Let's see:

        >>> orig = ['ala ma kota', 'a kot ma ale']
        >>> prox = crypto(orig)

    We can sill access all of the data through the proxy:

        >>> prox[0]
        'ala ma kota'

    But the whole repr() is now a bit different than usual:

        >>> prox
        ['nyn zn xbgn', 'n xbg zn nyr']
    """

    def __new__(proxy_cls, proxiee):
        """
        Create a new instance of ``proxy()`` wrapping ``proxiee``

        :param proxiee:
            The object to proxy
        :returns:
            An instance of new subclass of ``proxy``, called
            ``boundproxy[proxiee]`` that uses a new meta-class that lexically
            bounds the ``proxiee`` argument. The new sub-class has a different
            implementation of ``__new__`` and can be instantiated without
            additional arguments.
        """
        _logger.debug("__new__ on proxy with proxiee: %r", proxiee)
        boundproxy_meta = make_boundproxy_meta(proxiee)

        class boundproxy(proxy_cls, metaclass=boundproxy_meta):

            def __new__(boundproxy_cls):
                _logger.debug("__new__ on boundproxy %r", boundproxy_cls)
                return object.__new__(boundproxy_cls)
        return boundproxy()


def unproxied(fn):
    """
    Mark an object (attribute) as not-to-be-proxied.

    This decorator can be used inside :class:`proxy` sub-classes. Please
    consult the documentation of ``proxy`` for details.
    """
    fn.unproxied = True
    return fn
