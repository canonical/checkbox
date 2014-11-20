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
:mod:`pyglibc._subreaper` -- python wrapper around PR_SET_CHILD_SUBREAPER
=========================================================================

For more discussion of what a subreaper is, please consult the ``prctl(2)``
manual page and the following Linux kernel mailing thread:
    http://thread.gmane.org/gmane.linux.kernel/1236479
and the following LWN article:
    http://lwn.net/Articles/474787/
"""
from __future__ import absolute_import
from ctypes import addressof
from ctypes import c_int

from plainbox.vendor.glibc import PR_GET_CHILD_SUBREAPER
from plainbox.vendor.glibc import PR_SET_CHILD_SUBREAPER
from plainbox.vendor.glibc import prctl

__all__ = ['subreaper']


def _sr_unsupported():
    raise ValueError("PR_SET_CHILD_SUBREAPER is unsupported")


class _subreaper:
    """
    Pythonic wrapper around ``prctl(PR_{GET,SET}_CHILD_SUBREAPER, ...)``
    """
    SR_UNKNOWN = 0
    SR_UNSUPPORTED = 1
    SR_ENABLED = 2
    SR_DISABLED = 3

    _SR_STATUS_NAME = {
        SR_UNKNOWN: "unknown",
        SR_UNSUPPORTED: "unsupported",
        SR_ENABLED: "enabled",
        SR_DISABLED: "disabled"
    }

    __slots__ = ('_status',)

    def __init__(self):
        """
        Initialize a new subreaper object.

        Typically applications should not need to do this, there is a
        pre-initialized subreaper object available from this module.
        """
        self._status = self.SR_UNKNOWN

    def __repr__(self):
        return "<subreaper status:{}>".format(self.status_name)

    @property
    def status(self):
        """
        status of of the child sub-reaper flag

        Possible values are:

            SR_UNKNOWN:
                The current status of PR_SET_CHILD_SUBREAPER is unknown. Try
                setting or getting the :meth:`enabled` property to determine
                the status.
            SR_UNSUPPORTED:
                The PR_SET_CHILD_SUBREAPER option is not supported on this
                system. This feature requires Linux 3.4 or newer.
            SR_ENABLED:
                The PR_SET_CHILD_SUBREAPER option is supported and this flag
                is currently enabled.
            SR_DISABLED:
                The PR_SET_CHILD_SUBREAPER option is supported and this flag
                is currently disabled.
        """
        return self._status

    @property
    def status_name(self):
        """
        textual form of the current :meth:`status`, this is meant for debugging
        """
        return self._SR_STATUS_NAME[self._status]

    @property
    def enabled(self):
        """
        read or write the child sub-reaper flag of the current process

        This property behaves in the following manner:

        * If a read is attempted and a prior read or write has determined that
          this feature is unavailable (status is equal to ``SR_UNSUPPORTED``)
          then no further attempts are made and the outcome is ``False``.
        * If a read is attempted and the current status is ``SR_UNKNOWN`` then
          a ``prctl(PR_GET_CHILD_SUBREAPER, ...)`` call is made and the outcome
          depends on the returned value. If prctl fails then status is set to
          ``SR_UNSUPPORTED`` and the return value is ``False``. If the prctl
          call succeeds then status is set to either ``SR_ENABLED`` or
          ``SR_DISABLED`` and ``True`` or ``False`` is returned, respectively.
         * If a write is attempted and a prior read or write has determined
           that this feature is unavailable (status is equal to
           ``SR_UNSUPPORTED``) *and* the write would have enabled the flag, a
           ValueError is raised with an appropriate message. Otherwise a write
           is attempted. If the attempt to enable the flag fails a ValueError
           is raised, just as in the previous case.
         * If a write intending to disable the flag fails then this failure is
           silently ignored but status is set to ``SR_UNSUPPORTED``.
         * If a write succeeds then the status is set accordingly to
           ``SR_ENABLED`` or ``SR_DISABLED``, depending on the value written
           ``True`` or ``False`` respectively.

        In other words, this property behaves as if it was really calling
        prctl() but it is not going to repeat operations that will always fail.
        Nor will it ignore failures silently where that matters.
        """
        if self._status == self.SR_UNSUPPORTED:
            return False
        status = c_int()
        try:
            prctl(PR_GET_CHILD_SUBREAPER, addressof(status), 0, 0, 0)
        except OSError:
            self._status = self.SR_UNSUPPORTED
        else:
            self._status = self.SR_ENABLED if status else self.SR_DISABLED
            return self._status == self.SR_ENABLED

    @enabled.setter
    def enabled(self, status):
        if self._status == self.SR_UNSUPPORTED and status:
            _sr_unsupported()
        try:
            prctl(PR_SET_CHILD_SUBREAPER, 1 if status else 0, 0, 0, 0)
        except OSError:
            self._status = self.SR_UNSUPPORTED
        else:
            self._status = self.SR_ENABLED if status else self.SR_DISABLED
        if self._status == self.SR_UNSUPPORTED and status:
            _sr_unsupported()

    def __enter__(self):
        """
        """
        self.enabled = True

    def __exit__(self, *args):
        self.enabled = False


subreaper = _subreaper()
