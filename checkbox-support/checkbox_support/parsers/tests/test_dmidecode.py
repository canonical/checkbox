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
#
from io import StringIO

from unittest import TestCase

from checkbox.parsers.dmidecode import DmidecodeParser
from checkbox.parsers.tests.test_dmi import TestDmiMixin


FAKE_DMIDECODE = """\
# dmidecode 2.9
SMBIOS 2.4 present.

Handle 0x0000, DMI type 0, 24 bytes
BIOS Information
\tVendor: BIOS VENDOR
\tVersion: BIOS PRODUCT

Handle 0x0001, DMI type 1, 27 bytes
System Information
\tManufacturer: SYSTEM VENDOR
\tProduct Name: SYSTEM PRODUCT
\tSerial Number: SYSTEM SERIAL

Handle 0x0002, DMI type 2, 8 bytes
Base Board Information
\tManufacturer: Not Available
\tProduct Name: Not Available
\tSerial Number: Not Available

Handle 0x0003, DMI type 3, 13 bytes
Chassis Information
\tManufacturer: CHASSIS VENDOR
\tType: Notebook
\tSerial Number: Not Available
"""


class TestDmidecodeParser(TestCase, TestDmiMixin):

    def getParser(self):
        stream = StringIO(FAKE_DMIDECODE)
        return DmidecodeParser(stream)
