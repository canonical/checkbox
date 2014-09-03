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

import collections
import hashlib
import json
import logging
import string

from plainbox.i18n import gettext as _
from plainbox.impl import deprecated
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.plugins import PkgResourcesPlugInCollection
from plainbox.impl.secure.rfc822 import normalize_rfc822_value
from plainbox.impl.unit._legacy import UnitLegacyAPI
from plainbox.impl.unit._legacy import UnitWithIdLegacyAPI

__all__ = ['Unit']


logger = logging.getLogger("plainbox.unit")


def get_accessed_parameters(text):
    """
    Parse a new-style python string template and return parameter names

    :param text:
        Text string to parse
    :returns:
        A frozenset() with a list of names (or indices) of accessed parameters
    """
    # https://docs.python.org/3.4/library/string.html#string.Formatter.parse
    #
    # info[1] is the field_name (name of the referenced
    # formatting field) it _may_ be None if there are no format
    # parameters used
    return frozenset(
        info[1] for info in string.Formatter().parse(text)
        if info[1] is not None)


class Unit(UnitLegacyAPI):
    """
    Units are representations of data loaded from RFC822 definitions

    Units are used by plainbox to represent various important objects loaded
    from the filesystem. All units have identical representation (RFC822
    records) but each unit type has different semantics.

    .. warning::
        There is no metaclass to do it automatically yet so please be aware
        that the Unit.Meta class (which is a collection of metadata, not a
        meta-class) needs to be manually inherited in each subclass of the Unit
        class.
    """

    def __init__(self, data, raw_data=None, origin=None, provider=None,
                 parameters=None, field_offset_map=None):
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
        :param parameters:
            An (optional) dictionary of parameters. Parameters allow for unit
            properties to be altered while maintaining a single definition.
            This is required to obtain translated summary and description
            fields, while having a single translated base text and any
            variation in the available parameters.
        :param field_offset_map:
            An optional dictionary with offsets (in line numbers) of each field.
            Line numbers are relative to the value of origin.line_start
        """
        if raw_data is None:
            raw_data = data
        if origin is None:
            origin = Origin.get_caller_origin()
        if field_offset_map is None:
            field_offset_map = {field: 0 for field in data}
        self._data = data
        self._raw_data = raw_data
        self._origin = origin
        self._field_offset_map = field_offset_map
        self._provider = provider
        self._checksum = None
        self._parameters = parameters

    @classmethod
    def instantiate_template(cls, data, raw_data, origin, provider, parameters,
                             field_offset_map):
        """
        Instantiate this unit from a template.

        The point of this method is to have a fixed API, regardless of what the
        API of a particular unit class ``__init__`` method actually looks like.

        It is easier to standardize on a new method that to patch all of the
        initializers, code using them and tests to have an uniform initializer.
        """
        # This assertion is a low-cost trick to ensure that we override this
        # method in all of the subclasses to ensure that the initializer is
        # called with correctly-ordered arguments.
        assert cls is Unit, \
            "{}.instantiate_template() not customized".format(cls.__name__)
        return cls(data, raw_data, origin, provider, parameters,
                   field_offset_map)

    def __eq__(self, other):
        if not isinstance(other, Unit):
            return False
        return self.checksum == other.checksum

    def __ne__(self, other):
        if not isinstance(other, Unit):
            return True
        return self.checksum != other.checksum

    def __hash__(self):
        return hash(self.checksum)

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
    def field_offset_map(self):
        """
        The field-to-line-number-offset mapping.

        A dictionary mapping field name to offset (in lines) relative to the
        origin where that field definition commences.

        Note: the return value may be None
        """
        return self._field_offset_map

    @property
    def provider(self):
        """
        The provider object associated with this Unit
        """
        return self._provider

    @property
    def parameters(self):
        """
        The mapping of parameters supplied to this Unit

        This may be either a dictionary or None.

        .. seealso::
            :meth:`is_parametric()`
        """
        return self._parameters

    @property
    def is_parametric(self):
        """
        If true, then this unit is parametric

        Parametric units are instances of a template. To know which fields are
        constant and which are parametrized call the support method
        :meth:`get_accessed_parametes()`
        """
        return self._parameters is not None

    def get_accessed_parameters(self, *, force=False):
        """
        Get a set of attributes accessed from each template attribute

        :param force (keyword-only):
            If specified then it will operate despite being invoked on a
            non-parametric unit.  This is only intended to be called by
            TemplateUnit to inspect what the generated unit looks like in the
            early validation code.
        :returns:
            A dictionary of sets with names of attributes accessed by each
            template field. Note that for non-parametric Units the return value
            is always a dictionary of empty sets, regardless of how they actual
            parameter values look like.

        This function computes a dictionary of sets mapping from each template
        field (except from fields starting with the string 'template-') to a
        set of all the resource object attributes accessed by that element.
        """
        if force or self.is_parametric:
            return {
                key: get_accessed_parameters(value)
                for key, value in self._data.items()
            }
        else:
            return {key: frozenset() for key in self._data}

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
                   raw_data=changed_raw_data, provider=provider,
                   field_offset_map=record.field_offset_map)

    def get_record_value(self, name, default=None):
        """
        Obtain the normalized value of the specified record attribute

        :param name:
            Name of the field to access
        :param default:
            Default value, used if the field is not defined in the unit
        :returns:
            The value of the field, possibly with parameters inserted, or the
            default value
        :raises:
            KeyError if the field is parametrized but parameters are incorrect
        """
        value = self._data.get('_{}'.format(name))
        if value is None:
            value = self._data.get('{}'.format(name), default)
        if value is not None and self.is_parametric:
            value = string.Formatter().vformat(value, (), self.parameters)
        return value

    def get_raw_record_value(self, name, default=None):
        """
        Obtain the raw value of the specified record attribute

        :param name:
            Name of the field to access
        :param default:
            Default value, used if the field is not defined in the unit
        :returns:
            The raw value of the field, possibly with parameters inserted, or
            the default value
        :raises:
            KeyError if the field is parametrized but parameters are incorrect

        The raw value may have additional whitespace or indentation around the
        text. It will also not have the magic RFC822 dots removed. In general
        the text will be just as it was parsed from the unit file.
        """
        value = self._raw_data.get('_{}'.format(name))
        if value is None:
            value = self._raw_data.get('{}'.format(name), default)
        if value is not None and self.is_parametric:
            value = string.Formatter().vformat(value, (), self.parameters)
        return value

    def get_translated_record_value(self, name, default=None):
        """
        Obtain the translated value of the specified record attribute

        :param name:
            Name of the field/attribute to access
        :param default:
            Default value, used if the field is not defined in the unit
        :returns:
            The (perhaps) translated value of the field with (perhaps)
            parameters inserted, or the default value. The idea is to return
            the best value we can but there are no guarantees on returning a
            translated value.
        :raises:
            KeyError if the field is parametrized but parameters are incorrect
            This may imply that the unit is invalid but it may also imply that
            translations are broken. A malicious translation can break
            formatting and prevent an otherwise valid unit from working.
        """
        # Try to access the marked-for-translation record
        msgid = self._raw_data.get('_{}'.format(name))
        if msgid is not None:
            # We now have a translatable message that we can look up in the
            # provider translation database.
            msgstr = self.get_translated_data(msgid)
            assert msgstr is not None
            # We now have the translation _or_ the untranslated msgid again.
            # We can now normalize it so that it looks nice:
            msgstr = normalize_rfc822_value(msgstr)
            # We can now feed it through the template system to get parameters
            # inserted.
            if self.is_parametric:
                # This should not fail if the unit validates okay but it still
                # might fail due to broken translations. Perhaps we should
                # handle exceptions here and hint that this might be the cause
                # of the problem?
                msgstr = string.Formatter().vformat(
                    msgstr, (), self.parameters)
            return msgstr
        # If there was no marked-for-translation value then let's just return
        # the normal (untranslatable) version.
        msgstr = self._data.get(name)
        if msgstr is not None:
            # NOTE: there is no need to normalize anything as we already got
            # the non-raw value here.
            if self.is_parametric:
                msgstr = string.Formatter().vformat(
                    msgstr, (), self.parameters)
            return msgstr
        # If we have nothing better let's just return the default value
        return default

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
        text = canonical_form.encode('UTF-8')
        # Parametric units also get a copy of their parameters stored as an
        # additional piece of data
        if self.is_parametric:
            sorted_parameters = collections.OrderedDict(
                sorted(self.parameters.items()))
            canonical_parameters = json.dumps(
                sorted_parameters, indent=None, separators=(',', ':'))
            text += canonical_parameters.encode('UTF-8')
        # Compute the sha256 hash of the UTF-8 encoding of the canonical form
        # and return the hex digest as the checksum that can be displayed.
        return hashlib.sha256(text).hexdigest()

    @deprecated("0.7", "call unit.tr_unit() instead")
    def get_unit_type(self):
        return self.tr_unit()

    def get_translated_data(self, msgid):
        """
        Get a localized piece of data

        :param msgid:
            data to translate
        :returns:
            translated data obtained from the provider if this unit has one,
            msgid itself otherwise.
        """
        if msgid and self._provider:
            return self._provider.get_translated_data(msgid)
        else:
            return msgid

    def get_normalized_translated_data(self, msgid):
        """
        Get a localized piece of data and filter it with RFC822 parser
        normalization

        :param msgid:
            data to translate
        :returns:
            translated and normalized data obtained from the provider if this
            unit has one, msgid itself otherwise.
        """
        msgstr = self.get_translated_data(msgid)
        if msgstr is not None:
            return normalize_rfc822_value(msgstr)
        else:
            return msgid


# Collection of all unit classes
all_units = PkgResourcesPlugInCollection('plainbox.unit')


class UnitWithId(Unit, UnitWithIdLegacyAPI):
    """
    Base class for Units that have unique identifiers

    Unlike the JobDefintion class thepartial_id property has no fallback
    and is simply tied directly to the "id" field. The id property works
    in conjunction with a provider associated with the unit and simply adds
    the namespace part.
    """

    @property
    def partial_id(self):
        """
        Identifier of this category, without the provider name
        """
        return self.get_record_value('id')

    @property
    def id(self):
        if self.provider:
            return "{}::{}".format(self.provider.namespace, self.partial_id)
        else:
            return self.partial_id
