# -*- coding: utf-8 -*-
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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

from string import ascii_letters
from string import ascii_uppercase
import re


# Device string to match:
#   ⎡ Virtual core pointer                      id=2    [master pointer  (3)]
DEVICE_RE = re.compile(
    r""".+?(?P<name>[%s].+?) *\sid=(?P<id>\d+)"""
    % ascii_uppercase)

# Attribute string to match:
#   Buttons supported: 12
ATTRIBUTE_RE = re.compile(
    r"""(?P<key>[%s].+?): (?P<value>.+)"""
    % ascii_letters)

# Class string to match:
#   12. Type: XIButtonClass
CLASS_VALUE_RE = re.compile(
    r"""\d+\. Type: (?P<class>.+)""")

# List string to split:
#   "Button Horiz Wheel Right" None None
LIST_VALUE_RE = re.compile(
    r"""((?:[^ "]|"[^"]*")+)""")


class IXinputResult(object):
    """
    Base class for a result passed to the XinputParser run method.
    """

    def addXinputDevice(self, device):
        """Method to add an xinput device to this result."""

    def addXinputDeviceClass(self, device, device_class):
        """Method to add a class under an xinput device."""


class XinputParser(object):
    """
    Parser for the xinput command.
    """

    _key_map = {
        "Buttons supported": "buttons_supported",
        "Button labels": "button_labels",
        "Button state": "button_state",
        "Class originated from": "device_class",
        "Keycodes supported": "keycodes_supported",
        "Touch mode": "touch_mode",
        "Max number of touches": "max_touch",
        }

    def __init__(self, stream):
        """
        Construct a parser with the given stream.

        The stream is expected to contain the output of the command:
        xinput --list --long
        """
        self.stream = stream

    def _parseKey(self, key):
        """
        Parse the given key into a sanitized string.

        Returns a string in lower case without any spaces, or None if
        the key is not recognized.
        """
        if " " in key:
            return self._key_map.get(key)
        else:
            return key.lower()

    def _parseValue(self, value):
        """
        Parse the given value into a sanitized object.

        Returns a string with leading and trailing spaces stripped,
        or a list of the value contains double quotes, or None if the
        value is empty.
        """
        if value is not None:
            value = value.strip()
            if not value:
                return None

            match = CLASS_VALUE_RE.match(value)
            if match:
                return match.group("class")

            if '"' in value:
                return list(self._parseList(value))

        return value

    def _parseList(self, string):
        """
        Parse the given string into a list.

        The string can contain double quoted elements that are stripped
        of the quotes, or the string "None" that is replaced by None,
        or just space separated strings.
        """
        for element in LIST_VALUE_RE.split(string)[1::2]:
            if element.startswith('"') and element.endswith('"'):
                yield element.strip('"')
            elif element == "None":
                yield None

    def run(self, result):
        """
        Run the parser on the stream and add to the given result.

        The result is a derived instance of the IXinputResult base class
        to which results are added incrementally as the stream is parsed.
        """
        output = self.stream.read()
        for record in re.split(r"\n{2,}", output):
            record = record.strip()

            # Skip empty records
            if not record:
                continue

            lines = record.split("\n")

            # Parse device
            line = lines.pop(0)
            match = DEVICE_RE.match(line)
            if not match:
                continue

            device = {
                "id": int(match.group("id")),
                "name": match.group("name"),
                }
            result.addXinputDevice(device)

            # Parse device classes
            device_class = {}
            prefix = ""

            for line in lines:
                line = line.strip()

                # Skip lines with an unsupported attribute
                match = ATTRIBUTE_RE.match(line)
                if not match:
                    if line.startswith("Scroll"):
                        prefix = "scroll_"
                    elif line.startswith("Detail"):
                        prefix = "detail_"
                    continue

                # Skip lines with an unsupported key
                key = self._parseKey(match.group("key"))
                if not key:
                    continue

                value = self._parseValue(match.group("value"))

                # Special case for the class
                if key == "device_class" and device_class:
                    result.addXinputDeviceClass(device, device_class)
                    device_class = {}
                    prefix = ""

                device_class[prefix + key] = value

            if device_class:
                result.addXinputDeviceClass(device, device_class)

        return result
