# Copyright (c) 2014 Canonical Ltd.
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
:mod:`pyglibc.selectors` -- pyglib-based version of PEP3156 selectors
=====================================================================

This module contains a re-implementation of the :mod:`selectors` module from
Python's standard library as of Python 3.4. It is compatible with Python 2.7+
(including Python 3) and supports all of the features.

This module is considered stable public API. It will maintain backwards
compatibility for the foreseeable future. Any changes will be made to conform
more strictly with the original specification and the reference implementation
present in the python standard library.

Only features in scope for Linux are implemented. Obsolete select and poll
interfaces are not implemented. The API is deliberately kept identical to the
version from stdlib so that code can be ported from one to the other by mere
import swap.
"""
import abc
import collections
import sys

from plainbox.vendor.pyglibc import select
from plainbox.vendor.pyglibc._abc import Interface

__author__ = 'Zygmunt Krynicki <zygmunt.krynicki@canonical.com>'
__version__ = '1.0'  # Let's claim this is complete and fix issues, if any
__all__ = [
    'EVENT_READ',
    'EVENT_WRITE',
    'SelectorKey',
    'BaseSelector',
    'EpollSelector',
    'DefaultSelector'
]

EVENT_READ = 1
EVENT_WRITE = 2


SelectorKey = collections.namedtuple("SelectorKey", "fileobj fd events data")


class BaseSelector(Interface):
    """
    An abstract base class for all selectors.

    Unless otherwise stated, all selectors behave the same. They may differ in
    performance if a large number of selectors are being monitored. They may
    also differ in the resolution of the selector.
    """

    @abc.abstractproperty
    def resolution(self):
        """
        Smallest value of timeout supported.
        """

    @abc.abstractmethod
    def register(self, fileobj, events, data=None):
        """
        Register interest in specified IO events on the specified file object

        :param fileobj:
            Any existing file-like object that has a fileno() method
        :param events:
            A bitmask composed of EVENT_READ and EVENT_WRITE
        :param data:
            (optional) Arbitrary data
        :raises ValueError:
            if `fileobj` is invalid or not supported
        :raises KeyError:
            if the descriptor associated with `fileobj` is already registered.
        :returns:
            :class:`SelectorKey` associated with the passed arguments
        """

    @abc.abstractmethod
    def unregister(self, fileobj):
        """
        Remove interest in IO events from the specified fileobj

        :param fileobj:
            Any existing file-like object that has a fileno() method and was
            previously registered with :meth:`register()`
        :raises ValueError:
            if `fileobj` is invalid or not supported
        :raises KeyError:
            if the descriptor associated with `fileobj` is not registered.
        :returns:
            A :class:`SelectorKey` associated with the passed arguments
        """

    @abc.abstractmethod
    def modify(self, fileobj, events, data=None):
        """
        Modify interest in specified IO events on the specified file object

        :param fileobj:
            Any existing file-like object that has a fileno() method
        :param events:
            A bitmask composed of EVENT_READ and EVENT_WRITE
        :param data:
            (optional) Arbitrary data
        :raises ValueError:
            if `fileobj` is invalid or not supported
        :raises KeyError:
            if the descriptor associated with `fileobj` is not registered.
        :returns:
            The new :class:`SelectorKey` associated with the passed arguments
        """

    @abc.abstractmethod
    def select(self, timeout=None):
        """
        Wait until one or more of the registered file objects becomes ready
        or until the timeout expires.

        :param timeout:
            maximum wait time, in seconds (see below for special meaning)

        :returns:
            A list of pairs (key, events) for each ready file object.
            Note that the list may be empty if non-blocking behavior is
            selected or if the blocking wait is interrupted by a signal.

        The timeout argument has two additional special cases:

            1) If timeout is None then the call will block indefinitely
            2) If timeout <= 0 the call will never block
        """

    @abc.abstractmethod
    def close(self):
        """
        Close the selector

        This must be called to release resources that are associated with the
        selector.
        """

    @abc.abstractmethod
    def get_key(self, fileobj):
        """
        Get the SelectorKey associated with the specified file

        :returns:
            SelectorKey associated with fileobj
        :raises KeyError:
            if no such selector key exists
        """

    @abc.abstractmethod
    def get_map(self):
        """
        Return a Mapping of all the registered selectors.

        :returns:
            A map mapping registered file objects to their selectors.
        """

    @abc.abstractmethod
    def __enter__(self):
        """
        Enter a context manager.

        :returns:
            The selector object
        """

    @abc.abstractmethod
    def __exit__(self, *args):
        """
        Exit from a context manager.

        This method always calls :meth:`close()`
        """


class _EpollSelectorEvents(int):
    """
    Bit mask using ``EVENT_READ`` and ``EVENT_WRITE``.

    This class has useful __repr__() and supports conversions between
    epoll-specific masks and portable selector masks.
    """

    def __repr__(self):
        flags = []
        if self & EVENT_READ:
            flags.append('EVENT_READ')
        if self & EVENT_WRITE:
            flags.append('EVENT_WRITE')
        return ' | '.join(flags)

    @classmethod
    def from_epoll_events(cls, epoll_events):
        """
        Create a :class:`_EpollSelectorEvents` instance out of a bit mask using
        ``EPOLL*`` family of constants.
        """
        self = cls()
        if epoll_events & select.EPOLLIN:
            self |= EVENT_READ
        if epoll_events & select.EPOLLOUT:
            self |= EVENT_WRITE
        # Treat EPOLLHUP specially, as both 'read and write ready' so that on
        # the outside this can be interpreted as EOF
        if epoll_events & select.EPOLLHUP:
            self |= EVENT_READ | EVENT_WRITE
        return self

    def get_epoll_events(self):
        """
        Create a bit mask using ``EPOLL*`` family of constants.
        """
        epoll_events = 0
        if self & EVENT_READ:
            epoll_events |= select.EPOLLIN
        if self & EVENT_WRITE:
            epoll_events |= select.EPOLLOUT
        return epoll_events


def _get_fd(fileobj):
    """
    Get a descriptor out of a file object.

    :param fileobj:
        An integer (existing descriptor) or any object having the `fileno()`
        method.
    :raises ValueError:
        if the descriptor cannot be obtained or if the descriptor is invalid
    :returns:
        file descriptor number
    """
    if isinstance(fileobj, int):
        fd = fileobj
    else:
        try:
            fd = fileobj.fileno()
        except AttributeError:
            fd = None
    if fd is None or fd < 0:
        raise ValueError("invalid fileobj: {!r}".format(fileobj))
    return fd


class EpollSelector(BaseSelector):
    """
    A BaseSelector implemented using `select.epoll`
    """

    def __init__(self):
        """
        Initialize a new selector with a new ``select.epoll`` object.
        """
        self._fd_map = {}
        self._epoll = select.epoll()

    def __enter__(self):
        """
        Enter a context manager

        :returns:
            self
        :raises ValueError:
            If the underlying epoll object is closed
        """
        self._epoll.__enter__()
        return self

    def __exit__(self, *args):
        """
        Exit a context manager

        This method calls :meth:`close()`.
        """
        self.close()

    def fileno(self):
        """
        Get the descriptor number of the underlying epoll object

        :returns:
            The descriptor number
        :raises ValueError:
            If the underlying epoll object is closed
        """
        return self._epoll.fileno()

    def close(self):
        """
        Close the internal epoll object and clear the selector map

        :raises OSError:
            If the underlying ``close(2)`` fails. The error message matches
            those found in the manual page.
        """
        self._fd_map.clear()
        self._epoll.close()

    @property
    def resolution(self):
        """
        Smallest value of timeout supported.

        This is defined by ``epoll_wait(2)`` as one millisecond.
        """
        return 0.001

    def register(self, fileobj, events, data=None):
        """
        Register interest in specified IO events on the specified file object

        :param fileobj:
            Any existing file-like object that has a fileno() method
        :param events:
            A bitmask composed of EVENT_READ and EVENT_WRITE
        :param data:
            (optional) Arbitrary data
        :raises ValueError:
            if `fileobj` is invalid or not supported
        :raises KeyError:
            if the descriptor associated with `fileobj` is already registered.
        :returns:
            :class:`SelectorKey` associated with the passed arguments
        """
        fd = _get_fd(fileobj)
        epoll_events = _EpollSelectorEvents(events).get_epoll_events()
        if fd in self._fd_map:
            raise KeyError("{!r} is already registered".format(fileobj))
        key = SelectorKey(fileobj, fd, events, data)
        self._fd_map[fd] = key
        self._epoll.register(fd, epoll_events)
        return key

    def unregister(self, fileobj):
        """
        Remove interest in IO events from the specified fileobj

        :param fileobj:
            Any existing file-like object that has a fileno() method and was
            previously registered with :meth:`register()`
        :raises ValueError:
            if `fileobj` is invalid or not supported
        :raises KeyError:
            if the descriptor associated with `fileobj` is not registered.
        :returns:
            A :class:`SelectorKey` associated with the passed arguments
        """
        fd = _get_fd(fileobj)
        key = self._fd_map[fd]
        try:
            self._epoll.unregister(fd)
        except OSError:
            pass
        del self._fd_map[fd]
        return key

    def modify(self, fileobj, events, data=None):
        """
        Modify interest in specified IO events on the specified file object

        :param fileobj:
            Any existing file-like object that has a fileno() method
        :param events:
            A bitmask composed of EVENT_READ and EVENT_WRITE
        :param data:
            (optional) Arbitrary data
        :raises ValueError:
            if `fileobj` is invalid or not supported
        :raises KeyError:
            if the descriptor associated with `fileobj` is not registered.
        :returns:
            The new :class:`SelectorKey` associated with the passed arguments
        """
        fd = _get_fd(fileobj)
        epoll_events = _EpollSelectorEvents(events).get_epoll_events()
        if fd not in self._fd_map:
            raise KeyError("{!r} is not registered".format(fileobj))
        key = SelectorKey(fileobj, fd, events, data)
        self._fd_map[fd] = key
        self._epoll.modify(fd, epoll_events)
        return key

    def select(self, timeout=None):
        """
        Wait until one or more of the registered file objects becomes ready
        or until the timeout expires.

        :param timeout:
            maximum wait time, in seconds (see below for special meaning)

        :returns:
            A list of pairs (key, events) for each ready file object.
            Note that the list may be empty if non-blocking behavior is
            selected or if the blocking wait is interrupted by a signal.

        The timeout argument has two additional special cases:

            1) If timeout is None then the call will block indefinitely
            2) If timeout <= 0 the call will never block
        """
        if timeout is None:
            epoll_timeout = -1
        elif timeout <= 0:
            epoll_timeout = 0
        else:
            epoll_timeout = timeout
        max_events = len(self._fd_map) or -1
        result = []
        for fd, epoll_events in self._epoll.poll(epoll_timeout, max_events):
            key = self._fd_map.get(fd)
            events = _EpollSelectorEvents.from_epoll_events(epoll_events)
            events &= key.events
            if key:
                result.append((key, _EpollSelectorEvents(events)))
        return result

    def get_key(self, fileobj):
        """
        Get the SelectorKey associated with the specified file

        :returns:
            SelectorKey associated with fileobj
        :raises KeyError:
            if no such selector key exists
        """
        fd = _get_fd(fileobj)
        return self._fd_map[fd]

    def get_map(self):
        """
        Return a Mapping of all the registered selectors.

        :returns:
            A map mapping registered file objects to their selectors.
        """
        return self._fd_map


DefaultSelector = EpollSelector
