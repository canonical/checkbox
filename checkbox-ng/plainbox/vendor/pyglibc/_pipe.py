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
:mod:`pyglibc._pipe` -- python wrapper around pipe2
===================================================

This module exposes two functions :func:`pipe()` and :func:`pipe2()`. Both
functions have signatures identical to their counterparts in the standard
library of Python3.4. Both functions work on all supported versions of Python
(that is, 2.7 onwards)
"""
from __future__ import absolute_import

from ctypes import byref
from ctypes import c_int

from plainbox.vendor.glibc import O_CLOEXEC, pipe2 as _pipe2

__author__ = 'Zygmunt Krynicki <zygmunt.krynicki@canonical.com>'
__all__ = ['pipe', 'pipe2']


def pipe():
    """
    Wrapper around :func:`pipe2()`` with flags defaulting to ``O_CLOEXEC``.

    :returns:
        A pair of descriptors (read_end, write_end)
    """
    return pipe2(O_CLOEXEC)


def pipe2(flags=0):
    """
    Wrapper around ``pipe2(2)``

    :param flags:
        Optional flags to set. This should almost always include O_CLOEXEC so
        that the resulting code is not racy (see the discussion about O_CLOEXEC
        to understand why this flag is essential). It can also include
        O_NONBLOCK or O_DIRECT, depending on the desired behavior.
    :returns:
        A pair of descriptors (read_end, write_end)
    """
    pair = (c_int * 2)()
    _pipe2(byref(pair), flags)
    return pair[0], pair[1]
