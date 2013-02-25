# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox` -- main package
===============================

Simple checkbox redesign, without the complex message passing

All public API is in :mod:`plainbox.public`.
All abstract base classes are in :mod:`plainbox.abc`.
"""

import sys

if sys.version_info[0:2] < (3, 2):
    raise ImportError("plainbox requires python 3.2")  # pragma: no cover

# PEP386 compliant version declaration.
#
# This is used by @public decorator to enforce our public API guarantees.
__version__ = (0, 2, 0, "dev", 0)
