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
:mod:`pyglibc._signalfd` -- python wrapper around signalfd
==========================================================
"""
from __future__ import absolute_import
from __future__ import division

from ctypes import byref
from ctypes import sizeof
from threading import Lock

from plainbox.vendor.glibc import (
    SFD_CLOEXEC, SFD_NONBLOCK, sigset_t, signalfd_siginfo, sigemptyset,
    sigaddset, signalfd as _signalfd, read, close
)

__all__ = ['signalfd', 'SFD_CLOEXEC', 'SFD_NONBLOCK']


def _err_closed():
    raise ValueError("I/O operation on closed signalfd object")


class signalfd(object):
    """
    Pythonic wrapper around the ``signalfd(2)``
    """
    __slots__ = ('_sfd', '_signals')

    _close_lock = Lock()

    def __init__(self, signals=None, flags=0):
        """
        Create a signalfd() descriptor reacting to a set of signals.

        :param signals:
            A set of signal numbers to include in the mask of signals passed to
            signalfd(2).
        :param flags:
            A bit-mask of flags to pass to signalfd(2). You should pass
            SFD_CLOEXEC here, to ensure that a other threads don't inadvertedly
            fork and leak this descriptor. You can also pass SFD_NONBLOCK to
            make reads from the signalfd object non-blocking.
        """
        self._sfd = -1
        self._signals = frozenset()
        mask = sigset_t()
        sigemptyset(mask)
        if signals is None:
            signals = ()
        for signal in signals:
            sigaddset(mask, signal)
        self._sfd = _signalfd(-1, mask, flags)
        self._signals = frozenset(signals)

    def __repr__(self):
        if self._sfd < 0:
            return "<signalfd (closed)>"
        else:
            return "<signalfd fileno():{} signals:{}>".format(
                self.fileno(), self.signals)

    def __del__(self):
        self.close()

    def __enter__(self):
        """
        Enter a context manager

        :returns:
            self
        :raises ValueError:
            If :meth:`closed()` is True
        """
        if self._sfd < 0:
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
        Close the internal signalfd file descriptor if it isn't closed

        :raises OSError:
            If the underlying ``close(2)`` fails. The error message matches
            those found in the manual page.
        """
        with self._close_lock:
            sfd = self._sfd
            if sfd >= 0:
                self._sfd = -1
                self._signals = frozenset()
                close(sfd)

    @property
    def closed(self):
        """
        property indicating if the internal signalfd descriptor was closed
        """
        return self._sfd < 0

    @property
    def signals(self):
        """
        Get the set of monitored signals

        :returns:
            A frozenset corresponding to each of the monitored signals
        :raises ValueError:
            If :meth:`closed()` is True

        This property can be assigned to when it simply calls :meth:`update()`.
        """
        return self._signals

    @signals.setter
    def signals(self, signals):
        self.update(signals)

    def fileno(self):
        """
        Get the descriptor number obtained from ``signalfd(2)``

        :returns:
            The descriptor number
        :raises ValueError:
            If :meth:`closed()` is True
        """
        if self._sfd < 0:
            _err_closed()
        return self._sfd

    @classmethod
    def fromfd(cls, fd, signals):
        """
        Create a new signalfd object from a given file descriptor

        :param fd:
            A pre-made file descriptor obtained from ``signalfd_create(2)`
        :param signals:
            A pre-made frozenset that describes the monitored signals
        :raises ValueError:
            If fd is not a valid file descriptor
        :returns:
            A new signalfd object

        .. note::
            If the passed descriptor is incorrect then various methods will
            fail and raise OSError with an appropriate message.
        """
        if fd < 0:
            _err_closed()
        self = cls.__new__()
        object.__init__(self)
        self._sfd = fd
        self._signals = signals
        return self

    def update(self, signals):
        """
        Update the mask of signals this signalfd reacts to

        :param signals:
            A replacement set of signal numbers to monitor
        :raises ValueError:
            If :meth:`closed()` is True
        """
        if self._sfd < 0:
            _err_closed()
        mask = sigset_t()
        sigemptyset(mask)
        if signals is not None:
            for signal in signals:
                sigaddset(mask, signal)
        # flags are ignored when sfd is not -1
        _signalfd(self._sfd, mask, 0)
        self._signals = frozenset(signals)

    def read(self, maxsignals=None):
        """
        Read information about currently pending signals.

        :param maxsignals:
            Maximum number of signals to read. By default this is the same
            as the number of signals registered with this signalfd.
        :returns:
            A list of signalfd_siginfo object with information about most
            recently read signals. This list may be empty (in non-blocking
            mode).
        :raises ValueError:
            If :meth:`closed()` is True

        Read up to maxsignals recent pending singals ouf of the set of signals
        being monitored by this signalfd. If there are no signals yet and
        SFD_NONBLOCK was not passed to flags in :meth:`__init__()` then this
        call blocks until such signal is ready.
        """
        if maxsignals is None:
            maxsignals = len(self._signals)
        if maxsignals <= 0:
            raise ValueError("maxsignals must be greater than 0")
        info_list = (signalfd_siginfo * maxsignals)()
        num_read = read(self._sfd, byref(info_list), sizeof(info_list))
        return info_list[:num_read // sizeof(signalfd_siginfo)]
