#
# This file is part of Checkbox.
#
# Copyright 2011 Canonical Ltd.
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

import io
import re
from string import hexdigits
from string import ascii_uppercase

from checkbox_support.lib.dmi import Dmi
from checkbox_support.lib.dmi import DmiDevice


HANDLE_RE = re.compile(
    r"^Handle (?P<handle>0x[%s]{4}), "
    r"DMI type (?P<type>\d+), "
    r"(?P<size>\d+) bytes$"
    % hexdigits)
KEY_VALUE_RE = re.compile(
    r"^\t(?P<key>[%s].+):( (?P<value>.+))?$"
    % ascii_uppercase)


class DmiResult():

    """A simple class to store DMI devices."""

    def __init__(self):
        self.devices = []

    def addDmiDevice(self, device):
        self.devices.append(device)


class DmidecodeParser(object):
    """Parser for the dmidecode command."""

    _key_map = {
        "Form Factor": "form",
        "ID": "serial",
        "Manufacturer": "vendor",
        "Product Name": "name",
        "Serial Number": "serial",
        "Size": "size",
        "Type": "type",
        "Vendor": "vendor",
        "Version": "version",
        }

    def __init__(self, stream):
        self.stream = stream

    def _parseKey(self, key):
        return self._key_map.get(key)

    def _parseValue(self, value):
        if value is not None:
            value = value.strip()
            if not value:
                value = None

        return value

    def run(self, result):
        output = self.stream.read()
        for record in re.split(r"\n{2,}", output):
            record = record.strip()
            # Skip empty records
            if not record:
                continue

            # Skip header record
            lines = record.split("\n")
            line = lines.pop(0)
            if line.startswith("#"):
                continue

            # Skip records with an unsupported handle
            match = HANDLE_RE.match(line)
            if not match:
                continue

            # Skip records that are empty or inactive
            if not lines or lines.pop(0) == "Inactive":
                continue

            # Skip disabled entries and end-of-table marker
            type_index = int(match.group("type"))
            if type_index >= len(Dmi.type_names):
                continue

            category = Dmi.type_names[type_index]
            category = category.upper().split(" ")[-1]
            if category not in (
                    "BOARD", "BIOS", "CHASSIS", "DEVICE", "PROCESSOR",
                    "SYSTEM"):
                continue

            # Parse attributes
            attributes = {}

            for line in lines:
                # Skip lines with an unsupported key/value pair
                match = KEY_VALUE_RE.match(line)
                if not match:
                    continue

                # If the item has a supported key, use that one
                # instead of the "raw" DMI key.
                key = self._parseKey(match.group("key"))
                if not key:
                    # If not, then use the "raw" DMI key.
                    key = match.group("key").lower().replace(
                        " ", "_").replace("-", "_")

                key = "%s_%s" % (category.lower(), key)
                value = self._parseValue(match.group("value"))
                if value:
                    attributes[key] = value

            device = DmiDevice(attributes, category)
            result.addDmiDevice(device)

        return result


def parse_dmidecode_output(output):
    """
    Parse dmidecode output.

    :returns: a list of dicts containing DMI device data.
    The raw attributes are also printed.
    """
    stream = io.StringIO(output)
    modparser = DmidecodeParser(stream)
    result = DmiResult()
    modparser.run(result)
    return result.devices
