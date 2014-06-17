# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.unit` -- unit definition
============================================
"""

import logging
import collections
import hashlib
import json

from plainbox.i18n import gettext as _
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.plugins import PkgResourcesPlugInCollection


__all__ = ['Unit']


logger = logging.getLogger("plainbox.unit")


class Unit:
    """
    Units are representations of data loaded from RFC822 definitions

    Units are used by plainbox to represent various important objects loaded
    from the filesystem. All units have identical representation (RFC822
    records) but each unit type has different semantics.
    """

    def __init__(self, data, raw_data=None, origin=None, provider=None):
        """
        Initialize a new unit

        :param data:
            A dictionary of normalized data. This data is suitable for normal
            application usage. It is not suitable for gettext lookups as the
            original form is lost by the normalization process.
        :param raw_data:
            A dictionary of raw data (optional). Defaults to data. Values in
            this dictionary are in their raw form, as they were loaded from a
            unit file. This data is suitable for gettext lookups.
        :param origin:
            An (optional) Origin object. If omitted a fake origin object is
            created. Normally the origin object should be obtained from the
            RFC822Record object.
        """
        if raw_data is None:
            raw_data = data
        if origin is None:
            origin = Origin.get_caller_origin()
        self._data = data
        self._raw_data = raw_data
        self._origin = origin
        self._provider = provider
        self._checksum = None

    @property
    def unit(self):
        """
        the value of the unit field

        The default value is 'unit'. This property _may_ be overridden by
        certain subclasses but this behavior is not generally recommended.
        """
        return self.get_record_value('unit', "unit")

    @property
    def tr_unit(self):
        """
        Translated (optionally) value of the unit field
        """
        return self.get_record_value('unit', _("unit"))

    @property
    def origin(self):
        """
        The Origin object associated with this Unit
        """
        return self._origin

    @property
    def provider(self):
        """
        The provider object associated with this Unit
        """
        return self._provider

    @classmethod
    def from_rfc822_record(cls, record, provider=None):
        """
        Create a new Unit from RFC822 record. The resulting instance may not be
        valid but will always be created.

        :param record:
            A RFC822Record object
        :returns:
            A new Unit
        """
        # Strip the trailing newlines form all the raw values coming from the
        # RFC822 parser. We don't need them and they don't match gettext keys
        # (xgettext strips out those newlines)
        changed_raw_data = {
            key: value.rstrip('\n')
            for key, value in record.raw_data.items()
        }
        return cls(record.data, origin=record.origin,
                   raw_data=changed_raw_data, provider=provider)

    def get_record_value(self, name, default=None):
        """
        Obtain the normalized value of the specified record attribute
        """
        value = self._data.get('_{}'.format(name))
        if value is None:
            value = self._data.get('{}'.format(name), default)
        return value

    def get_raw_record_value(self, name, default=None):
        """
        Obtain the raw value of the specified record attribute

        The raw value may have additional whitespace or indentation around the
        text. It will also not have the magic RFC822 dots removed. In general
        the text will be just as it was parsed from the unit file.
        """
        value = self._raw_data.get('_{}'.format(name))
        if value is None:
            value = self._raw_data.get('{}'.format(name), default)
        return value

    def validate(self, **validation_kwargs):
        """
        Validate data stored in the unit

        :param validation_kwargs:
            Validation parameters (may vary per subclass)
        :raises ValidationError:
            If the unit is incorrect somehow.
        """

    @property
    def checksum(self):
        """
        Checksum of the unit definition.

        This property can be used to compute the checksum of the canonical form
        of the unit definition. The canonical form is the UTF-8 encoded JSON
        serialization of the data that makes up the full definition of the unit
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
        sorted_data = collections.OrderedDict(sorted(self._data.items()))
        # Compute the canonical form which is arbitrarily defined as sorted
        # json text with default indent and separator settings.
        canonical_form = json.dumps(
            sorted_data, indent=None, separators=(',', ':'))
        # Compute the sha256 hash of the UTF-8 encoding of the canonical form
        # and return the hex digest as the checksum that can be displayed.
        return hashlib.sha256(canonical_form.encode('UTF-8')).hexdigest()

    def get_unit_type(self):
        return self.get_record_value('unit', _("unit"))


# Collection of all unit classes
all_units = PkgResourcesPlugInCollection('plainbox.unit')
