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
:mod:`plainbox.impl.commands` -- shared code for plainbox sub-commands
======================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from abc import abstractmethod, ABCMeta


class PlainBoxCommand(metaclass=ABCMeta):
    """
    Simple interface class for plainbox commands
    """

    @abstractmethod
    def invoked(self, ns):
        """
        Implement what should happen when the command gets invoked

        The ns is the namespace produced by argument parser
        """

    @abstractmethod
    def register_parser(self, subparsers):
        """
        Implement what should happen to register the additional parser for this
        command. The subparsers argument is the return value of
        ArgumentParser.add_subparsers()
        """
