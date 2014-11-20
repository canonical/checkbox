# Copyright (c) 2014 Canonical Ltd.
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
:mod:`pyglibc._abc` -- an abc.ABCMeta derived base class
========================================================

This module provides the ``Interface`` class which is using the built-in
abc.ABCMeta metaclass. The general idea is to abstract away the differences in
python 2 and python 3 metaclass declaration syntax.
"""
from __future__ import absolute_import

import abc
import sys

__author__ = 'Zygmunt Krynicki <zygmunt.krynicki@canonical.com>'
__all__ = [
    'Interface',
]

if sys.version_info[0] == 2:
    Interface = type("Interface", (object,), {
        "__doc__": "An empty class with :class:`abc.ABCMeta` metaclass.",
        "__metaclass__": abc.ABCMeta,
    })
else:
    Interface = abc.ABCMeta("Interface", (), {
        "__doc__": "An empty class with :class:`abc.ABCMeta` metaclass.",
    })
