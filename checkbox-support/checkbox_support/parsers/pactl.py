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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


"""
:mod:`checkbox_support.parsers.pactl` -- `pactl list` parser
============================================================

Parser for the output of ``pactl list`` syntax.

The abstract syntax tree of 'pactl list' is as follows::

    Document: Record + ('\n' + Record)*

    Record: RECORD-NAME ':' Attribute+

    Attribute: ATTRIBUTE-NAME ':' AttributeValue

    AttributeValue: SIMPLE-VALUE '\n'
                    | PropertyValue
                    | VOLUME-VALUE
                    | BASE-VOLUME-VALUE
                    | PORT+
                    | PORT-WITH-PROFILE+

    PropertyValue: PROPERTY-NAME '=' PROPERTY-VALUE

    (other all-upsercase values are not specified in detail)

Some parts of the output  are always localized while others depend on the
locale of the current user. This is caused by the fact that ``pactl`` talks to
pulse audio server over DBus. Some of the data obtained from pulse that was is
localized and it is difficult to influence. This should be of no problem for
the parser but actual usage of the data can be more difficult.
"""

from collections import OrderedDict
from inspect import isroutine

import pyparsing as p


# Enable packrat paring.
#
# This reduces the complexity of the parser
# from O(2**N) to O(N) at the cost of memory O(N) vs O(1).
p.ParserElement.enablePackrat()

# XXX: Hack, changes global stuff
#
# This makes pyparsing not so ignorant to whitespace. Normally pyparsing is
# happily treating newlines, tabs, spaces and carriage returns as irrelevant
# spacers between tokens. Because pactl syntax is so whitespace-sensitive this
# is globally turned off. A proper solution would apply this on a
# per-ParserElement level
p.ParserElement.DEFAULT_WHITE_CHARS = " "


def class_with_syntax(cls):
    """
    Decorator for classes with a __syntax__ attribute.

    Helps to setup the `Syntax` attribute using the special `__syntax__`
    attribute. It also calls from_tokens() with the appropriate class.
    """
    if hasattr(cls, '__syntax__'):
        cls.Syntax = (
            cls.__syntax__
        ).setParseAction(
            cls.from_tokens
        ).parseWithTabs()
    return cls


class Node:
    """
    Base class for things parsed by pyparsing.

    Defines sensible __repr__(), __init__() and from_tokens(). That
    last class method uses __fragments__ to pick things from pyparsing
    ParseResults and assign them to attributes of the Node instance.

    This serves as a buffer between pyparsing and external code, so that
    anything we do to the syntax is irrelevant as long as the tree of
    Nodes remains the same.
    """

    __fragments__ = {}

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)

    def __repr__(self):
        return "{}({})".format(
            type(self).__name__, ", ".join([
                "{}={!r}".format(attr, getattr(self, attr))
                for attr in self.__fragments__]))

    @classmethod
    def from_tokens(cls, tokens):
        """
        Create a node from tokens that were matched from __syntax__
        """
        data = {
            attr: mapper(tokens) if isroutine(mapper) else tokens[mapper]
            for attr, mapper in cls.__fragments__.items()
        }
        return cls(**data)


@class_with_syntax
class Property(Node):
    """
    A key=value pair.

    A list of properties is a possible syntax for Attribute value.
    """

    __fragments__ = {
        'name': 'property-name',
        'value': 'property-value'
    }

    __syntax__ = (
        p.Word(p.alphanums + "-_.").setResultsName("property-name")
        + p.Suppress('=')
        + p.QuotedString('"').setResultsName("property-value")
    ).setResultsName('property')


@class_with_syntax
class Profile(Node):
    """
    Description of a pulseaudio profile.
    """

    __fragments__ = {
        'name': 'profile-name',
        'label': 'profile-label',
        'sink_cnt': 'profile-sink-count',
        'source_cnt': 'profile-source-count',
        'priority': 'profile-priority',
    }

    __syntax__ = (
        p.Word(p.alphanums + "+-:").setParseAction(
            lambda t: t[0].rstrip(':')
        ).setResultsName("profile-name")
        + p.delimitedList(
            p.Literal("(HDMI)") | p.Literal("(IEC958)") | p.Regex('[^ (\n]+'),
            ' ', combine=True
        ).setResultsName('profile-label')
        + p.Suppress('(')
        + p.Keyword('sinks').suppress()
        + p.Suppress(':')
        + p.Word(p.nums).setParseAction(
            lambda t: int(t[0])
        ).setResultsName('profile-sink-count')
        + p.Suppress(',')
        + p.Keyword('sources').suppress()
        + p.Suppress(':')
        + p.Word(p.nums).setParseAction(
            lambda t: int(t[0])
        ).setResultsName('profile-source-count')
        + p.Suppress(',')
        + p.Keyword('priority').suppress()
        + p.MatchFirst([
            p.Suppress('.'),
            # Merged on 2013-06-03 (YYYY-MM-DD)
            # http://cgit.freedesktop.org/pulseaudio/pulseaudio/commit/src/utils/pactl.c?id=83c3cf0a65fb05900f81bd2dbb38e6956eb23935
            p.Suppress(':'),
        ])
        + p.Word(p.nums).setParseAction(
            lambda t: int(t[0])
        ).setResultsName('profile-priority')
        + p.Suppress(')')
    ).setResultsName("profile")


@class_with_syntax
class Port(Node):
    """
    Description of a port on a sink
    """

    __fragments__ = {
        'name': 'port-name',
        'label': 'port-label',
        'priority': 'port-priority',
        'availability': 'port-availability'
    }

    __syntax__ = (
        p.Word(p.alphanums + "-;").setResultsName('port-name')
        + p.Suppress(':')
        # This part was very tricky to write. The label is basically
        # arbitrary localized Unicode text.  We want to grab all of it in
        # one go but without consuming the upcoming '(' character or the
        # space that comes immediately before.
        #
        # The syntax here combines a sequence of words, as defined by
        # anything other than a space and '(', delimited by a single
        # whitespace.
        + p.delimitedList(
            p.Regex('[^ (\n]+'), ' ', combine=True
        ).setResultsName('port-label')
        + p.Suppress('(')
        + p.Keyword('priority').suppress()
        + p.Suppress(':')
        + p.Word(p.nums).setParseAction(
            lambda t: int(t[0])
        ).setResultsName('port-priority')
        + p.MatchFirst([
            p.Suppress(',') + p.Literal('not available'),
            p.Suppress(',') + p.Literal('available'),
            p.Empty().setParseAction(lambda t: '')
        ]).setResultsName('port-availability')
        + p.Suppress(')')
    ).setResultsName("port")


# =================
# Shared Attributes
# =================

PropertyAttributeValue = (
    p.Group(
        p.OneOrMore(
            p.LineStart().suppress()
            + p.Optional(p.White('\t')).suppress()
            + p.Optional(Property.Syntax)
            + p.LineEnd().suppress()
        )
    ).setResultsName("attribute-value"))


@class_with_syntax
class PortWithProfile(Node):
    """
    Variant of :class:`Port` that is used by "card" records inside
    the "Ports" property. It differs from the normal port syntax by having
    different entries inside the last section. Availability is not listed
    here, only priority. Priority does not have a colon before the actual
    number. This port is followed by profile assignment.
    """
    __fragments__ = {
        'name': 'port-name',
        'label': 'port-label',
        'priority': 'port-priority',
        'latency_offset': 'port-latency-offset',
        'availability': 'port-availability',
        'properties': lambda t: t['port-properties'].asList(),
        'profile_list': lambda t: t['port-profile-list'].asList(),
    }

    __syntax__ = (
        p.Word(p.alphanums + "-;").setResultsName('port-name')
        + p.Suppress(':')
        # This part was very tricky to write. The label is basically arbitrary
        # localized Unicode text. We want to grab all of it in one go but
        # without consuming the upcoming and latest '(' character or the space
        # that comes immediately before.
        #
        # The syntax here combines a sequence of words, as defined by anything
        # other than a space and '(', delimited by a single whitespace.
        + p.Combine(
            p.OneOrMore(
                ~p.FollowedBy(
                    p.Regex('\(.+?\)')
                    + p.LineEnd()
                )
                + p.Regex('[^ \n]+')
                + p.White().suppress()
            ),
            ' '
        ).setResultsName('port-label')
        + p.Suppress('(')
        + p.Keyword('priority').suppress()
        + p.Optional(
            p.Suppress(':')
        )
        + p.Word(p.nums).setParseAction(
            lambda t: int(t[0])
        ).setResultsName('port-priority')
        + p.Optional(
            p.MatchFirst([
                p.Suppress(',') + p.Keyword('latency offset:').suppress()
                + p.Word(p.nums).setParseAction(lambda t: int(t[0]))
                + p.Literal("usec").suppress(),
                p.Empty().setParseAction(lambda t: '')
            ]).setResultsName('port-latency-offset')
        )
        + p.Optional(
            p.MatchFirst([
                p.Suppress(',') + p.Literal('not available'),
                p.Suppress(',') + p.Literal('available'),
                p.Empty().setParseAction(lambda t: '')
            ]).setResultsName('port-availability')
        )
        + p.Suppress(')')
        + p.LineEnd().suppress()
        + p.Optional(
            p.MatchFirst([
                p.LineStart().suppress()
                + p.NotAny(p.White(' '))
                + p.White('\t').suppress()
                + p.Keyword('Properties:').suppress()
                + p.LineEnd().suppress()
                + PropertyAttributeValue,
                p.Empty().setParseAction(lambda t: [])
            ]).setResultsName('port-properties')
        )
        + p.White('\t', max=3).suppress()
        + p.Literal("Part of profile(s)").suppress()
        + p.Suppress(":")
        + p.delimitedList(
            p.Word(p.alphanums + "+-:"), ", "
        ).setResultsName("port-profile-list")
    ).setResultsName("port")


# =========================
# Non-collection attributes
# =========================

AttributeName = p.Regex("[a-zA-Z][^:\n]+").setResultsName("attribute-name")


VolumeAttributeValue = (
    p.Combine(
        p.Or([
            p.Literal("(invalid)"),
            p.Regex("([0-9]+: +[0-9]+% ?)+")
        ])
        + p.LineEnd()
        + p.Optional(p.White('\t').suppress())
        + p.Or([
            p.Literal("(invalid)"),
            p.Regex("([0-9]+: -?[0-9]+\.[0-9]+ dB ?)+")
        ])
        + p.LineEnd()
        + p.Optional(p.White('\t').suppress())
        + p.Regex("balance [0-9]+\.[0-9]+")
        + p.LineEnd(),
        adjacent=False
    ).setResultsName("attribute-value")
)


BaseVolumeAttributeValue = (
    p.Combine(
        p.Regex("[0-9]+%")
        + p.LineEnd()
        + p.Optional(p.White('\t').suppress())
        + p.Regex("-?[0-9]+\.[0-9]+ dB")
        + p.LineEnd(),
        adjacent=False
    ).setResultsName("attribute-value")
)


SimpleAttributeValue = (
    p.Regex("[^\n]*").setResultsName("attribute-value")
    + p.LineEnd().suppress())

# simple values
GenericSimpleAttributeValue = p.MatchFirst([
    VolumeAttributeValue,
    BaseVolumeAttributeValue,
    SimpleAttributeValue,
])


@class_with_syntax
class GenericSimpleAttribute(Node):

    __fragments__ = {
        'name': 'attribute-name',
        'value': 'attribute-value',
    }

    __syntax__ = (
        p.LineStart().suppress()
        + p.NotAny(p.White(' '))
        + p.Optional(p.White('\t')).suppress()
        + AttributeName
        + p.Literal(':').suppress()
        + GenericSimpleAttributeValue
    ).setResultsName("attribute")


# =====================
# Collection Attributes
# =====================

PortsAttributeValue = (
    p.Group(
        p.OneOrMore(
            p.LineStart().suppress()
            + p.Optional(p.White('\t')).suppress()
            + Port.Syntax
            + p.LineEnd().suppress())
    ).setResultsName("attribute-value"))

PortsWithProfilesAttributeValue = (
    p.Group(
        p.OneOrMore(
            p.LineStart().suppress()
            + p.Optional(p.White('\t')).suppress()
            + PortWithProfile.Syntax
            + p.LineEnd().suppress())
    ).setResultsName("attribute-value"))

FormatsAttributeValue = (
    p.Group(
        p.OneOrMore(
            p.LineStart().suppress()
            + p.Optional(p.White('\t')).suppress()
            + p.Word(p.alphas)
            + p.LineEnd().suppress())
    ).setResultsName("attribute-value"))

ProfilesAttributeValue = (
    p.Group(
        p.OneOrMore(
            p.LineStart().suppress()
            + p.Optional(p.White('\t')).suppress()
            + Profile.Syntax
            + p.LineEnd().suppress())
    ).setResultsName("attribute-value"))


GenericListAttributeValue = p.MatchFirst([
    PortsAttributeValue,
    PropertyAttributeValue,
    PortsWithProfilesAttributeValue,
    ProfilesAttributeValue,
    FormatsAttributeValue,
])


@class_with_syntax
class GenericListAttribute(Node):

    __fragments__ = {
        'name': 'attribute-name',
        'value': lambda t: t['attribute-value'].asList()
    }

    __syntax__ = (
        p.LineStart().suppress()
        + p.NotAny(p.White(' '))
        + p.Optional(p.White('\t')).suppress()
        + AttributeName
        + p.Literal(':').suppress()
        + p.LineEnd().suppress()
        + GenericListAttributeValue
    ).setResultsName("attribute")


@class_with_syntax
class Record(Node):
    """
    Single standalone entry of `pactl list`.

    The record is composed of a name and a list of attributes.  Pulseaudio
    exposes objects such as cards, sinks and sources as separate records.

    Each attribute may be of a different type. Some attributes are simple
    values while others have finer structure, including lits and even
    additional recursive attributes.
    """

    __fragments__ = {
        'name': 'record-name',
        'attribute_list': lambda t: t['record-attributes'].asList(),
        'attribute_map': lambda t: OrderedDict(
            (attr.name, attr)
            for attr in t['record-attributes'].asList()),
    }

    __syntax__ = (
        p.LineStart()
        + p.NotAny(p.White(' \t'))
        + p.Regex("[A-Z][a-zA-Z ]+ #[0-9]+").setResultsName("record-name")
        + p.LineEnd().suppress()
        + p.OneOrMore(
            p.Or([
                GenericListAttribute.Syntax,
                GenericSimpleAttribute.Syntax,
            ])
        ).setResultsName("record-attributes")
    ).setResultsName("record")

    def as_json(self):
        return {
            'name': self.name,
            'attribute_list': self.attribute_list,
        }

    def __repr__(self):
        # Custom __repr__ that skips attribute_map
        return "{}({})".format(
            type(self).__name__, ", ".join([
                "{}={!r}".format(attr, getattr(self, attr))
                for attr in ['name', 'attribute_list']]))


@class_with_syntax
class Document(Node):
    """
    Encompasses whole output of `pactl list`
    The document is composed of a list of :class:`Record` objects
    """

    __fragments__ = {
        'record_list': lambda t: t['record-list'].asList(),
    }

    __syntax__ = (
        p.OneOrMore(
            Record.Syntax + p.Optional("\n").suppress()
        ).setResultsName("record-list")
    ).parseWithTabs()


def parse_pactl_output(output):
    """
    Parse output of `LANG=C pactl list`

    :returns: :class:`Document` object that corresponds to the parsed input
    """
    return Document.Syntax.parseString(output, parseAll=True)[0]
