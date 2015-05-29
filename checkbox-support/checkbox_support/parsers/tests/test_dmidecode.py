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

from io import StringIO
from unittest import TestCase

from checkbox_support.parsers.dmidecode import DmidecodeParser
from checkbox_support.parsers.tests.test_dmi import TestDmiMixin, DmiResult


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

REAL_DMIDECODE = """\
Handle 0x000B, DMI type 1, 27 bytes
System Information
\tManufacturer: LENOVO
\tProduct Name: 20AMOS3
\tVersion: ThinkPad X240
\tSerial Number: PF04B4D
\tUUID: 170AFF01-52A1-11CB-A7A6-EB7272884401
\tWake-up Type: Power Switch
\tSKU Number: LENOVO_MT_20AM
\tFamily: ThinkPad X240

Handle 0x003A, DMI type 0, 24 bytes
BIOS Information
\tVendor: LENOVO
\tVersion: GIET53WW (2.01 )
\tRelease Date: 07/23/2013
\tAddress: 0xE0000
\tRuntime Size: 128 kB
\tROM Size: 16384 kB
\tCharacteristics:
\t\tPCI is supported
\t\tPNP is supported
\t\tBIOS is upgradeable
\t\tBIOS shadowing is allowed
\t\tBoot from CD is supported
\t\tSelectable boot is supported
\t\tACPI is supported
\t\tUSB legacy is supported
\t\tBIOS boot specification is supported
\t\tTargeted content distribution is supported
\t\tUEFI is supported
\tBIOS Revision: 2.1
\tFirmware Revision: 1.7
"""

class TestDmidecodeArtificialParser(TestCase, TestDmiMixin):

    def getParser(self):
        stream = StringIO(FAKE_DMIDECODE)
        return DmidecodeParser(stream)

class TestDmidecodeRealParser(TestCase):

    """
    Test class for real data.

    The main goal is to test parsing of attributes like BIOS characteristics
    and firmware revision data, but also to ensure that all custom attributes
    are loaded.
    """

    def getParser(self):
        stream = StringIO(REAL_DMIDECODE)
        return DmidecodeParser(stream)

    def getResult(self):
        parser = self.getParser()
        result = DmiResult()
        parser.run(result)
        return result

    def test_devices(self):
        result = self.getResult()
        self.assertEqual(len(result.devices), 2)

    def test_bios(self):
        """Test data, including raw attributes, from real BIOS dump."""
        result = self.getResult()
        device = result.getDevice("BIOS")
        self.assertTrue(device)
        # If the device nas no "name", extracted from the
        # "Product Name" attribute, then the "product" will
        # be the "Version" attribute instead.
        self.assertEqual(device.product, "GIET53WW (2.01 )")
        self.assertEqual(device.vendor, "LENOVO")
        self.assertEqual(device.serial, None)
        # For more generic access to DMI data, the raw_attributes
        # property allows access to arbitrary data items.
        # Note that in here, we lose the "mapping several possible
        # DMI keys to a single well-known key" functionality, but it
        # makes it possible to access any item from dmi parsing.
        expected_attrs = ['version', 'rom_size', 'vendor', 'firmware_revision',
                          'release_date', 'address', 'bios_revision',
                          'runtime_size']
        self.assertEqual(sorted(expected_attrs),
                         sorted(device.raw_attributes.keys()))
        self.assertEqual(device.raw_attributes['firmware_revision'], "1.7")
        self.assertEqual(device.raw_attributes['bios_revision'], "2.1")
        self.assertEqual(device.raw_attributes['address'], "0xE0000")
        self.assertEqual(device.raw_attributes['release_date'], "07/23/2013")

    def test_system(self):
        """Test data, including raw attributes, from real SYSTEM dump."""
        result = self.getResult()
        device = result.getDevice("SYSTEM")
        self.assertTrue(device)
        self.assertEqual(device.product, "20AMOS3")
        self.assertEqual(device.vendor, "LENOVO")
        self.assertEqual(device.serial, "PF04B4D")
        self.assertEqual(device.raw_attributes['sku_number'], "LENOVO_MT_20AM")
        self.assertEqual(device.raw_attributes['uuid'],
                         "170AFF01-52A1-11CB-A7A6-EB7272884401")
