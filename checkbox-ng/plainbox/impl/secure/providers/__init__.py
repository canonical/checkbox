# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.secure.providers` -- providers package
==========================================================

Providers are a mechanism by which PlainBox can enumerate jobs and test plans.
Currently there are only v1 (as in version one) providers that basically have
to behave as CheckBox itself (mini CheckBox forks for example)

V1 providers
------------

The first (current) version of PlainBox providers has the following properties,
this is also described by :class:`plainbox.abc.IProvider1`::

    * there is a directory with '.txt' or '.txt.in' files with RFC822-encoded
      job definitions. The definitions need a particular set of keys to work.

    * there is a directory with additional executables (added to PATH)

    * there is a directory with an additional python3 libraries (added to
      PYTHONPATH)
"""


class ProviderNotFound(LookupError):
    """
    Exception used to report that a provider cannot be located
    """
