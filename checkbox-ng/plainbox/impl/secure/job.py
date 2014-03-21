# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.secure.job` -- secure code for job definitions
==================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import collections
import hashlib
import json
import re


class BaseJob:
    """
    Base Job definition class.
    """

    def __init__(self, data, raw_data=None):
        """
        Initialize a new BaseJob object

        :param data:
            A dictionary of normalized data.

            This data is suitable for normal application usage. It is not
            suitable for gettext lookups as the original form is lost by the
            normalization process.

        :param raw_data:
            A dictionary of raw data (optional). Defaults to data.

            Data in this dictionary is in its raw form, as it was written in a
            job definition file. This data is suitable for gettext lookups.
        """
        self.__data = data
        if raw_data is None:
            raw_data = data
        self.__raw_data = raw_data
        self._checksum = None

    @property
    def _data(self):
        raise AttributeError("Hey, poking at _data is forbidden!")

    def get_record_value(self, name, default=None):
        """
        Obtain the normalized value of the specified record attribute
        """
        value = self.__data.get('_{}'.format(name))
        if value is None:
            value = self.__data.get('{}'.format(name), default)
        return value

    def get_raw_record_value(self, name, default=None):
        """
        Obtain the raw value of the specified record attribute

        The raw value may have additional whitespace or indentation around the
        text. It will also not have the magic RFC822 dots removed. In general
        the text will be just as it was parsed from a job definition file.
        """
        value = self.__raw_data.get('_{}'.format(name))
        if value is None:
            value = self.__raw_data.get('{}'.format(name), default)
        return value

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
        Compute the value for :attr:`checksum`.
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
