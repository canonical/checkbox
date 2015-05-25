# This file is part of Checkbox.
#
# Copyright 2011-2015 Canonical Ltd.
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
Parsers for OEM image information.

There are 3 possible attachments containing data relevant to OEM images::

    * /etc/buildstamp
    * recovery_info_attachment
    * dell_bto_xml_attachment

A class is provided to parse each of these.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
from xml.dom import minidom
from xml.parsers.expat import ExpatError


class ImageInfoResult():

    """
    A simple class to hold image information results.

    It has methods for all the parser classes in this module so it can be
    easily reused.

    """

    def __init__(self):
        self.image_info = {}

    def addBuildstampInfo(self, data):
        """Add the given buildstamp."""
        self.image_info['buildstamp'] = data

    def addImageVersionInfo(self, key, data):
        """Add image version data under the given key."""
        self.image_info[key] = data


class BtoInfoResult():

    """A simple class to hold BTO information results."""

    def __init__(self):
        self.bto_info = {}

    def addBtoInfo(self, key, data):
        """Add bto data under the given key."""
        self.bto_info[key] = data


class BuildstampParser():

    """
    Parser for the info/buildstamp attachment.

    Buildstamp is quite unstructured, so the parser is very simple, it will
    just verify that the attachment contains exactly 2 lines and call the
    addBuildstamp method of the resutl class with the entire content of the
    second line.
    """

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """Parse stream and set the buildstamp in the result."""
        buildstamp = ""
        for index, line in enumerate(self.stream):
            if index == 1:
                buildstamp = line
            if index >= 2 and line.strip() != '':
                # It contains more than 2 non-blank
                # lines, so exit right now,
                # this attachment looks bogus.
                return
        if buildstamp.strip():
            result.addBuildstampInfo(buildstamp.strip())


class RecoveryInfoParser():

    """
    Parser for recovery_info.

    Recovery_info can contain two keys: image_version and bto_version.

    """

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """Parse stream and set the version attributes in the result."""
        for line in self.stream:
            try:
                key, value = line.split(":", 1)
            except (ValueError, AttributeError):
                # Just skip this line
                pass
            else:
                key = key.strip()
                value = value.strip()
                if key in ("image_version", "bto_version") and value:
                    result.addImageVersionInfo(key, value)


class BtoParser():

    """Parser for Dell bto.xml data file."""

    def __init__(self, stream):
        self.stream = stream

    def run(self, result):
        """
        Parse stream and set bto attributes in the result.

        Possible BTO attributes are (the result.addBtoInfo method will be
        called with each key/value)::

            * iso - a single string with the name of the installed ISO
            * generator - a single string
            * bootstrap - a single string
            * ubiquity - a single string
            * base - a single string, presumably name of ISO on which this
              project is based
            * fish. A list of strings with fish packages (they're .debs)
        """
        try:
            bto_dom = minidom.parse(self.stream)
        except ExpatError:
            # Bogus data, give up silently
            return
        for key in ['iso', 'generator', 'bootstrap',
                    'ubiquity', 'base', 'driver']:
            elems = bto_dom.getElementsByTagName(key)
            items = [item.firstChild.data for item in elems
                     if hasattr(item.firstChild, 'data')]
            if len(items) == 1:
                result.addBtoInfo(key, items[0])
            elif len(items) > 1:
                result.addBtoInfo(key, items)


def parse_buildstamp_attachment_output(output):
    """Parse info/buildstamp attachment output."""
    stream = io.StringIO(output)
    parser = BuildstampParser(stream)
    result = ImageInfoResult()
    parser.run(result)
    return result.image_info['buildstamp']


def parse_bto_attachment_output(output):
    """Parse bto.xml attachment output."""
    stream = io.StringIO(output)
    parser = BtoParser(stream)
    result = BtoInfoResult()
    parser.run(result)
    return result.bto_info


def parse_recovery_info_attachment_output(output):
    """Parse recovery_info attachment output."""
    stream = io.StringIO(output)
    parser = RecoveryInfoParser(stream)
    result = ImageInfoResult()
    parser.run(result)

    return {k: result.image_info[k]
            for k in result.image_info.keys()
            if k in ("bto_version", "image_version")}
