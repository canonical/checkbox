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
:mod:`pyglibc.select` -- pyglibc-based pure-python select.py
============================================================

This module contains a re-implementation of the :mod:`select` module from
Python's standard library as of Python 3.4. It is compatible with Python 2.7+
(including Python 3) and supports all of the features (including setting
close-on-exec flags).

This module is considered stable public API. It will maintain backwards
compatibility for the foreseeable future. Any changes will be made to conform
more strictly with the original specification and the reference implementation
present in the python standard library.

Only features in scope for Linux are implemented. Obsolete select and poll
interfaces are not implemented. The API is deliberately kept identical to the
version from stdlib so that code can be ported from one to the other by mere
import swap.
"""
from __future__ import absolute_import

from ctypes import POINTER
from ctypes import byref
from ctypes import cast
from errno import EBADF
from threading import Lock

from plainbox.vendor.glibc import EPOLLERR
from plainbox.vendor.glibc import EPOLLET
from plainbox.vendor.glibc import EPOLLHUP
from plainbox.vendor.glibc import EPOLLIN
from plainbox.vendor.glibc import EPOLLMSG
from plainbox.vendor.glibc import EPOLLONESHOT
from plainbox.vendor.glibc import EPOLLOUT
from plainbox.vendor.glibc import EPOLLPRI
from plainbox.vendor.glibc import EPOLLRDBAND
from plainbox.vendor.glibc import EPOLLRDHUP
from plainbox.vendor.glibc import EPOLLRDNORM
from plainbox.vendor.glibc import EPOLLWRBAND
from plainbox.vendor.glibc import EPOLLWRNORM
from plainbox.vendor.glibc import EPOLL_CLOEXEC
from plainbox.vendor.glibc import EPOLL_CTL_ADD
from plainbox.vendor.glibc import EPOLL_CTL_DEL
from plainbox.vendor.glibc import EPOLL_CTL_MOD
from plainbox.vendor.glibc import FD_SETSIZE
from plainbox.vendor.glibc import close
from plainbox.vendor.glibc import epoll_create1
from plainbox.vendor.glibc import epoll_ctl
from plainbox.vendor.glibc import epoll_event
from plainbox.vendor.glibc import epoll_wait

__author__ = 'Zygmunt Krynicki <zygmunt.krynicki@canonical.com>'
__version__ = '1.0'  # Let's claim this is complete and fix issues, if any
__all__ = ['epoll', 'EPOLL_CLOEXEC', 'EPOLLIN', 'EPOLLOUT', 'EPOLLPRI',
           'EPOLLERR', 'EPOLLHUP', 'EPOLLET', 'EPOLLONESHOT', 'EPOLLRDNORM',
           'EPOLLRDBAND', 'EPOLLWRNORM', 'EPOLLWRBAND', 'EPOLLMSG']

# NOTE: Extra features not present in Python 3.4
__all__ += ['EPOLLRDHUP']


def _err_closed():
    raise ValueError("I/O operation on closed epoll object")


class epoll(object):
    """
    Pure-python reimplementation of  :class:`select.epoll` from Python 3.4
    compatible with Python 2.7+.
    """
    # Somewhat inefficient lock acquired on each call to epoll.close() to
    # ensure that we match semantics from python stdlib where close can be
    # called concurrently.
    _close_lock = Lock()

    def __init__(self, sizehint=-1, flags=0):
        """
        :param sizehint:
            Dummy argument for compatibility with select.epoll, ignored.
        :param flags:
            Flags passed to ``epoll_create1()``. Note that internally flags are
            always OR-ed with EPOLL_CLOEXEC, matching what Python 3.4 does, so
            passing 0 is perfectly fine.
        """
        self._epfd = -1
        self._epfd = epoll_create1(flags | EPOLL_CLOEXEC)

    def __enter__(self):
        """
        Enter a context manager

        :returns:
            self
        :raises ValueError:
            If :meth:`closed()` is True
        """
        if self._epfd < 0:
            _err_closed()
        return self

    def __exit__(self, *args):
        """
        Exit a context manager

        This method calls :meth:`close()`.
        """
        self.close()

    def close(self):
        """
        Close the internal epoll file descriptor if it isn't closed

        :raises OSError:
            If the underlying ``close(2)`` fails. The error message matches
            those found in the manual page.
        """
        with self._close_lock:
            epfd = self._epfd
            if epfd >= 0:
                self._epfd = -1
                close(epfd)

    @property
    def closed(self):
        """
        property indicating if the internal epoll descriptor was closed
        """
        return self._epfd < 0

    def fileno(self):
        """
        Get the descriptor number obtained from ``epoll_create1()(2)``

        :returns:
            The descriptor number
        :raises ValueError:
            If :meth:`closed()` is True
        """
        if self._epfd < 0:
            _err_closed()
        return self._epfd

    @classmethod
    def fromfd(cls, fd):
        """
        Create a new epoll object from a given file descriptor

        :param fd:
            A pre-made file descriptor obtained from ``epoll_create(2)`` or
            ``epoll_create1(2)``
        :raises ValueError:
            If fd is not a valid file descriptor
        :returns:
            A new epoll object

        .. note::
            If the passed descriptor is incorrect then various methods will
            fail and raise OSError with an appropriate message.
        """
        if fd < 0:
            _err_closed()
        self = cls.__new__()
        object.__init__(self)
        self._epfd = fd
        return self

    def register(self, fd, eventmask=None):
        """
        Register a new descriptor

        :param fd:
            The descriptor to register.
        :param eventmask:
            Bit-mask of events that will be monitored. By default EPOLLIN,
            EPOLLOUT and EPOLLPRI are used. Note that EPOLLHUP is implicit and
            doesn't need to be provided.
        :raises ValueError:
            If :meth:`closed()` is True
        :raises OSError:
            If the underlying ``epoll_ctl(2)`` fails. The error message matches
            those found in the manual page.
        """
        if self._epfd < 0:
            _err_closed()
        if eventmask is None:
            eventmask = EPOLLIN | EPOLLOUT | EPOLLPRI
        ev = epoll_event()
        ev.events = eventmask
        ev.data.fd = fd
        epoll_ctl(self._epfd, EPOLL_CTL_ADD, fd, byref(ev))

    def unregister(self, fd):
        """
        Unregister a previously registered descriptor

        :param fd:
            The descriptor to unregister
        :raises ValueError:
            If :meth:`closed()` is True
        :raises OSError:
            If the underlying ``epoll_ctl(2)`` fails. The error message matches
            those found in the manual page.

        .. note::
            For feature parity with Python 3.4, unlike what ``epoll_ctl(2)``
            would do, we are silently ignoring ``EBADF`` which is raised if
        """
        if self._epfd < 0:
            _err_closed()
        ev = epoll_event()
        try:
            epoll_ctl(self._epfd, EPOLL_CTL_DEL, fd, byref(ev))
        except OSError as exc:
            # Allow fd to be closed, matching Python 3.4
            if exc.errno != EBADF:
                raise

    def modify(self, fd, eventmask):
        """
        Change the bit-mask of events associated with a previously-registered
        descriptor.

        :param fd:
            The descriptor to modify.
        :param eventmask:
            New bit-mask of events that will be monitored.
        :raises ValueError:
            If :meth:`closed()` is True
        :raises OSError:
            If the underlying ``epoll_ctl(2)`` fails. The error message matches
            those found in the manual page.
        """
        if self._epfd < 0:
            _err_closed()
        ev = epoll_event()
        ev.events = eventmask
        ev.data.fd = fd
        epoll_ctl(self._epfd, EPOLL_CTL_MOD, fd, byref(ev))

    def poll(self, timeout=-1, maxevents=-1):
        """
        Poll for events

        :param timeout:
            The amount of seconds to wait for events before giving up. The
            default value, -1, represents infinity. Note that unlike the
            underlying ``epoll_wait()`` timeout is a fractional number
            representing **seconds**.
        :param maxevents:
            The maximum number of events to report. The default is a
            reasonably-sized maximum, identical to the one selected by
            Python 3.4.
        :returns:
            A list of (fd, events) that were reported or an empty list if the
            timeout elapsed.
        :raises ValueError:
            If :meth:`closed()` is True
        :raises OSError:
            If the underlying ``epoll_wait(2)`` fails. The error message
            matches those found in the manual page.
        """
        if self._epfd < 0:
            _err_closed()
        if timeout != -1:
            # 1000 because epoll_wait(2) uses milliseconds
            timeout = int(timeout * 1000)
        if maxevents == -1:
            maxevents = FD_SETSIZE - 1
        events = (epoll_event * maxevents)()
        num_events = epoll_wait(
            self._epfd, cast(byref(events), POINTER(epoll_event)),
            maxevents, timeout)
        return [(events[i].data.fd, events[i].events)
                for i in range(num_events)]
