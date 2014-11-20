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
:mod:`pyglibc` -- pythonic wrappers around glibc
================================================

This package builds upon the ``glibc`` module and provides high-level Pythonic
APIs for some of the features of glibc. Where possible some of the wrappers are
modeled after existing modules in the Python 3.4 standard libary so those can
be a more universally available, glibc-specific, drop-in replacement.
"""
from __future__ import absolute_import

from plainbox.vendor.pyglibc import select
from plainbox.vendor.pyglibc import selectors
from plainbox.vendor.pyglibc._pipe import pipe, pipe2
from plainbox.vendor.pyglibc._pthread_sigmask import pthread_sigmask
from plainbox.vendor.pyglibc._signalfd import signalfd
from plainbox.vendor.pyglibc._subreaper import subreaper

__author__ = 'Zygmunt Krynicki <zygmunt.krynicki@canonical.com>'
__version__ = '0.6'
__all__ = [
    'pipe',
    'pipe2',
    'pthread_sigmask',
    'select',
    'selectors',
    'signalfd',
    'subreaper',
]
