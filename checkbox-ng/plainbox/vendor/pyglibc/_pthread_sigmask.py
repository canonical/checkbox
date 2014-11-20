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
:mod:`pyglibc._pthread_sigmask` -- python wrapper around pthread_sigmask
========================================================================

.. warning::
    ``pthread_sigmask(2)`` operates on the mask of flags associated with the
    calling thread. Therefore there are no thread safety considerations as the
    whole object is inherently unsafe (or thread-specific).
"""
from __future__ import absolute_import

from plainbox.vendor.glibc import (
    NSIG, SIG_BLOCK, SIG_UNBLOCK, SIG_SETMASK, sigset_t, sigemptyset,
    sigaddset, sigismember, pthread_sigmask as _pthread_sigmask)

__all__ = ['pthread_sigmask']


class pthread_sigmask(object):
    """
    Pythonic wrapper around the ``pthread_sigmask(2)``
    """

    __slots__ = ('_signals', '_setmask', '_mask', '_old_mask', '_is_active')

    def __init__(self, signals=None, setmask=False):
        """
        Initialize a new pthread_sigmask object.

        :param signals:
            List of signals to block
        :param setmask:
            A flag that controls if ``SIG_SETMASK`` should be used over
            ``SIG_BLOCK`` and ``SIG_UNBLOCK``.  For details see :meth:`block()`
            and :meth:`unblock()`.

        .. note::
            ``pthread_sigmask(2)`` is not called until :meth:`block()` is
            called.
        """
        if signals is None:
            self._signals = frozenset()
        else:
            self._signals = frozenset(signals)
        self._setmask = setmask
        self._mask = sigset_t()
        self._old_mask = None  # old mask is only used for SIG_SETMASK
        self._is_active = False
        sigemptyset(self._mask)
        for signal in self.signals:
            sigaddset(self._mask, signal)

    def __repr__(self):
        return "<pthread_sigmask signals:{} mode:{} active:{}>".format(
            self._signals,
            "SIG_SETMASK" if self._setmask else "SIG_BLOCK",
            "yes" if self.is_active else "no")

    def __enter__(self):
        """
        Part of the context manager protocol.

        This method calls :meth:`block()`.

        :returns:
            self
        """
        self.block()
        return self

    def __exit__(self, *args):
        """
        Part of the context manager protocol.

        This method calls :meth:`unblock()`.
        """
        self.unblock()

    @property
    def is_active(self):
        """
        Flag that remebers if the signals are blocked.

        If is_active is True, modifications to :meth:`signals` are applied
        instantly.
        """
        return self._is_active

    @property
    def signals(self):
        """
        associated set of blocked signals

        :returns:
            The frozenset of signals associated with this pthread_sigmask.

        .. note::
            Whether the signals returned by this method are currently blocked
            or not depends on the circumstances. They can be assumed to be
            blocked after :meth:`block()` returns but any code running after
            that may alter the effective mask thus rendering this value stale.

        This property can be assigned to. Doing so while :meth:`is_active` is
        True will update the effective mask on the fly. Otherwise modifications
        are buffered until :meth:`enter()` is first called.
        """
        return self._signals

    @signals.setter
    def signals(self, new_signals):
        # Convert signals to frozendict as we depend on that below
        new_signals = frozenset(new_signals)
        # Reset the mask to what signals describes
        sigemptyset(self._mask)
        for signal in new_signals:
            sigaddset(self._mask, signal)
        # If we're active, re-apply the changes
        if self.is_active:
            # In setmask mode we can just overwrite the old values directly
            if self._setmask:
                # NOTE: we're not updating self._old_mask here. This way
                # unblock will trully restore everything despite modifications
                # to signals that happened after the call to block()
                _pthread_sigmask(SIG_SETMASK, self._mask, None)
            else:
                # in the non-setmask mode, let's just apply the delta
                delta_mask = sigset_t()
                # Let's start blocking the new signals first
                added_signals = new_signals - self._signals
                if added_signals:
                    sigemptyset(delta_mask)
                    for signal in added_signals:
                        sigaddset(delta_mask, signal)
                        _pthread_sigmask(SIG_BLOCK, delta_mask, None)
                # Let's unblock signals next
                removed_signals = self._signals - new_signals
                if removed_signals:
                    sigemptyset(delta_mask)
                    for signal in removed_signals:
                        sigaddset(delta_mask, signal)
                        _pthread_sigmask(SIG_UNBLOCK, delta_mask, None)
        # Reset signals to the new value
        self._signals = new_signals

    def block(self):
        """
        Use ``pthread_sigmask(2)`` to block signals.

        This method uses either ``SIG_SETMASK`` or ``SIG_BLOCK``, depending on
        how the object was constructed. After this method is called, the
        subsequent call to :meth:`unblock()` will undo its effects.

        .. note::
            This method is a no-op if signal blocking is currently active (as
            determined by :meth:`is_active` returning True).
        """
        if self._is_active:
            return
        if self._setmask:
            self._old_mask = sigset_t()
            sigemptyset(self._old_mask)
            _pthread_sigmask(SIG_SETMASK, self._mask, self._old_mask)
        else:
            _pthread_sigmask(SIG_BLOCK, self._mask, None)
        self._is_active = True

    def unblock(self):
        """
        Use ``pthread_sigmask(2)`` to unblock signals.

        :raises ValueError:
            If the old mask is not obtained yet. This only happens in when
            ``setmask=True`` was passed to the initializer and ``unblock()`` is
            called before ``block()`` was called.

        This method uses either ``SIG_SETMASK`` or ``SIG_UNBLOCK``, depending
        on how the object was constructed. Actual behavior differs as explained
        below. In both cases the term *old mask* refers to the effective mask
        that was obtained at the time :meth:`block()` was called.

        - In the ``SIG_SETMASK`` mode the old mask is restored (overwrite)
        - In the ``SIG_UNBLOCK`` mode the old mask is ignored and the desired
          signals are unblocked (incremental change)

        .. note::
            This method is a no-op if signal blocking is currently inactive (as
            determined by :meth:`is_active` returning False).
        """
        if not self._is_active:
            return
        if self._setmask:
            if self._old_mask is None:
                raise ValueError("block() wasn't called yet!")
            _pthread_sigmask(SIG_SETMASK, self._old_mask, None)
            self._old_mask = None
        else:
            _pthread_sigmask(SIG_UNBLOCK, self._mask, None)
        self._is_active = False

    @classmethod
    def get(cls):
        """
        Use ``pthread_sigmask(2)`` to obtain the mask of blocked signals

        :returns:
            A fresh :class:`pthread_sigmask` object.

        The returned object behaves as it was constructed with the list of
        currently blocked signals, ``setmask=False`` and as if the
        :meth:`block()` was immediately called.

        That is, calling :meth:`unblock()` will will cause those signals not to
        be blocked anymore while calling :meth:`block()` will re-block them (if
        they were unblocked after this method returns).
        """
        mask = sigset_t()
        sigemptyset(mask)
        _pthread_sigmask(0, None, mask)
        signals = []
        for sig_num in range(1, NSIG):
            if sigismember(mask, sig_num):
                signals.append(sig_num)
        self = cls(signals)
        self._is_active = True
        self._old_mask = mask
        return self
