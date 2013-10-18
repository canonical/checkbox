# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.secure.job` -- secure code for job definitions
==================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import collections
import hashlib
import json
import os
import re


class BaseJob:
    """
    Base Job definition class.
    """

    def __init__(self, data):
        self.__data = data
        self._checksum = None

    @property
    def _data(self):
        raise AttributeError("Hey, poking at _data is forbidden!")

    def get_record_value(self, name, default=None):
        """
        Obtain the value of the specified record attribute
        """
        return self.__data.get(name, default)

    @property
    def plugin(self):
        return self.get_record_value('plugin')

    @property
    def command(self):
        return self.get_record_value('command')

    @property
    def environ(self):
        return self.get_record_value('environ')

    @property
    def user(self):
        return self.get_record_value('user')

    def get_checksum(self):
        """
        Compute a checksum of the job definition.

        """
        return self.checksum

    @property
    def checksum(self):
        """
        Checksum of the job definition.

        This property can be used to compute the checksum of the canonical form
        of the job definition. The canonical form is the UTF-8 encoded JSON
        serialization of the data that makes up the full definition of the job
        (all keys and values). The JSON serialization uses no indent and
        minimal separators.

        The checksum is defined as the SHA256 hash of the canonical form.
        """
        if self._checksum is None:
            self._checksum = self._compute_checksum()
        return self._checksum

    def _compute_checksum(self):
        """
        Compute the value for :meth:`get_checksum()` and :attr:`checksum`.
        """
        # Ideally we'd use simplejson.dumps() with sorted keys to get
        # predictable serialization but that's another dependency. To get
        # something simple that is equally reliable, just sort all the keys
        # manually and ask standard json to serialize that..
        sorted_data = collections.OrderedDict(sorted(self.__data.items()))
        # Compute the canonical form which is arbitrarily defined as sorted
        # json text with default indent and separator settings.
        canonical_form = json.dumps(
            sorted_data, indent=None, separators=(',', ':'))
        # Compute the sha256 hash of the UTF-8 encoding of the canonical form
        # and return the hex digest as the checksum that can be displayed.
        return hashlib.sha256(canonical_form.encode('UTF-8')).hexdigest()

    def get_environ_settings(self):
        """
        Return a set of requested environment variables
        """
        if self.environ is not None:
            return {variable for variable in re.split('[\s,]+', self.environ)}
        else:
            return set()

    def modify_execution_environment(self, environ, packages):
        """
        Compute the environment the script will be executed in
        """
        # Get a proper environment
        env = dict(os.environ)
        # Use non-internationalized environment
        env['LANG'] = 'C.UTF-8'
        # Create CHECKBOX*_SHARE for every checkbox related packages
        # Add their respective script directory to the PATH variable
        # giving precedence to those located in /usr/lib/
        for path in packages:
            basename = os.path.basename(path)
            env[basename.upper().replace('-', '_') + '_SHARE'] = path
            # Update PATH so that scripts can be found
            env['PATH'] = os.pathsep.join([
                os.path.join('usr', 'lib', basename, 'bin'),
                os.path.join(path, 'scripts')]
                + env.get("PATH", "").split(os.pathsep))
        if 'CHECKBOX_DATA' in env:
            env['CHECKBOX_DATA'] = environ['CHECKBOX_DATA']
        # Add new environment variables only if they are defined in the
        # job environ property
        for key in self.get_environ_settings():
            if key in environ:
                env[key] = environ[key]
        return env
