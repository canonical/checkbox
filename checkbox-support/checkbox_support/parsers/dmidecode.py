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

from string import hexdigits
from string import ascii_uppercase
import re

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


class DmidecodeParser(object):
    """Parser for the dmidecode command."""

    _key_map = {
        "ID": "serial",
        "Manufacturer": "vendor",
        "Product Name": "name",
        "Serial Number": "serial",
        "Type": "type",
        "Vendor": "vendor",
        "Version": "version",
        "Size": "size",
        "Form Factor": "form",
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
                "BOARD", "BIOS", "CHASSIS", "DEVICE", "PROCESSOR", "SYSTEM"):
                continue

            # Parse attributes
            attributes = {}

            for line in lines:
                # Skip lines with an unsupported key/value pair
                match = KEY_VALUE_RE.match(line)
                if not match:
                    continue

                # Skip lines with an unsupported key
                key = self._parseKey(match.group("key"))
                if not key:
                    continue

                key = "%s_%s" % (category.lower(), key)
                value = self._parseValue(match.group("value"))
                attributes[key] = value

            device = DmiDevice(attributes, category)
            result.addDmiDevice(device)

        return result
