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
plainbox.impl
=============

Internal implementation of plainbox

 * THIS MODULE DOES NOT HAVE STABLE PUBLIC API *
"""

from plainbox.abc import ITestDefinition


class TestDefinition(ITestDefinition):

    @property
    def plugin(self):
        return self._data['plugin']

    @property
    def name(self):
        return self._data['name']

    @property
    def requires(self):
        return self._data['requires']

    @property
    def command(self):
        return self._data['command']

    @property
    def description(self):
        return self._data['description']

    def __init__(self, data):
        self._data = data

    @classmethod
    def from_rfc822_record(cls, record):
        """
        Create a TestDefinition instance from rfc822 record
        """
        for key in ['plugin', 'name', 'requires', 'command', 'description']:
            if key not in record:
                raise ValueError(
                    "Required record key {!r} was not found".format(key))
        return cls(record)
