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
plainbox.impl.job
=================

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

import logging

from plainbox.abc import IJobDefinition
from plainbox.impl.resource import ResourceProgram


logger = logging.getLogger("plainbox.job")


class JobDefinition(IJobDefinition):

    @property
    def plugin(self):
        return self.__getattr__('plugin')

    @property
    def name(self):
        return self.__getattr__('name')

    @property
    def requires(self):
        try:
            return self.__getattr__('requires')
        except AttributeError:
            return None

    @property
    def command(self):
        try:
            return self.__getattr__('command')
        except AttributeError:
            return None

    @property
    def description(self):
        try:
            return self.__getattr__('description')
        except AttributeError:
            return None

    @property
    def depends(self):
        try:
            return [name.strip()
                    for name in self.__getattr__('depends').split(',')]
        except AttributeError:
            return None

    def __init__(self, data):
        self._data = data
        self._resource_program = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<JobDefinition name:{!r} plugin:{!r}>".format(
            self.name, self.plugin)

    def __getattr__(self, attr):
        if attr in self._data:
            return self._data[attr]
        gettext_attr = "_{}".format(attr)
        if gettext_attr in self._data:
            value = self._data[gettext_attr]
            # TODO: feed through gettext
            return value
        raise AttributeError(attr)

    def get_resource_program(self):
        """
        Return a ResourceProgram based on the 'requires' expression.

        The program instance is cached in the JobDefinition and is not
        compiled or validated on subsequent calls.

        Returns ResourceProgram or None
        Raises ResourceProgramError or SyntaxError
        """
        if self.requires is not None and self._resource_program is None:
            self._resource_program = ResourceProgram(self.requires)
        return self._resource_program

    @classmethod
    def from_rfc822_record(cls, record):
        """
        Create a JobDefinition instance from rfc822 record
        """
        for key in ['plugin', 'name']:
            if key not in record:
                raise ValueError(
                    "Required record key {!r} was not found".format(key))
        return cls(record)
