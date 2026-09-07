# This file is part of Checkbox.
#
# Copyright 2008-2022 Canonical Ltd.
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

import os

from checkbox_ng.support.lib.conversion import string_to_type


# See also 7.4.1 "System Enclosure or Chassis Types" of the "System Management
# BIOS Specification, Version 3.9.0" (DSP0134), available
# from https://www.dmtf.org/standards/smbios.
class Dmi:
    chassis_types = (
        "Undefined",  # 0x00 placeholder for SMBIOS alignment
        "Other",
        "Unknown",
        "Desktop",
        "Low Profile Desktop",
        "Pizza Box",
        "Mini Tower",
        "Tower",
        "Portable",
        "Laptop",
        "Notebook",
        "Hand Held",
        "Docking Station",
        "All In One",
        "Sub Notebook",
        "Space-saving",
        "Lunch Box",
        "Main Server Chassis",
        "Expansion Chassis",
        "Sub Chassis",
        "Bus Expansion Chassis",
        "Peripheral Chassis",
        "RAID Chassis",
        "Rack Mount Chassis",
        "Sealed-case PC",
        "Multi-system",
        "Compact PCI",
        "Advanced TCA",
        "Blade",
        "Blade Enclosure",
        "Tablet",
        "Convertible",
        "Detachable",
        "IoT Gateway",
        "Embedded PC",
        "Mini PC",
        "Stick PC",
    )

    type_names = (
        "BIOS",  # 0x00
        "System",
        "Base Board",
        "Chassis",
        "Processor",
        "Memory Controller",
        "Memory Module",
        "Cache",
        "Port Connector",
        "System Slots",
        "On Board Devices",
        "OEM Strings",
        "System Configuration Options",
        "BIOS Language",
        "Group Associations",
        "System Event Log",
        "Physical Memory Array",
        "Memory Device",
        "32-bit Memory Error",
        "Memory Array Mapped Address",
        "Memory Device Mapped Address",
        "Built-in Pointing Device",
        "Portable Battery",
        "System Reset",
        "Hardware Security",
        "System Power Controls",
        "Voltage Probe",
        "Cooling Device",
        "Temperature Probe",
        "Electrical Current Probe",
        "Out-of-band Remote Access",
        "Boot Integrity Services",
        "System Boot",
        "64-bit Memory Error",
        "Management Device",
        "Management Device Component",
        "Management Device Threshold Data",
        "Memory Channel",
        "IPMI Device",
        "Power Supply",
    )


class DmiDevice:

    bus = "dmi"
    driver = None
    product_id = None
    vendor_id = None

    _product_blacklist = (
        "<BAD INDEX>",
        "N/A",
        "Not Available",
        "INVALID",
        "OEM",
        "Product Name",
        "System Product Name",
        "To be filled by O.E.M.",
        "To Be Filled By O.E.M.",
        "To Be Filled By O.E.M. by More String",
        "Unknown",
        "Uknown",
        "Unknow",
        "xxxxxxxxxxxxxx",
    )
    _vendor_blacklist = (
        "<BAD INDEX>",
        "Not Available",
        "OEM",
        "OEM Manufacturer",
        "System manufacturer",
        "System Manufacturer",
        "System Name",
        "To be filled by O.E.M.",
        "To Be Filled By O.E.M.",
        "To Be Filled By O.E.M. by More String",
        "Unknow",  # XXX This is correct mispelling
        "Unknown",
    )
    _serial_blacklist = (
        "0",
        "00000000",
        "00 00 00 00 00 00 00 00",
        "0123456789",
        "Base Board Serial Number",
        "Chassis Serial Number",
        "N/A",
        "None",
        "Not Applicable",
        "Not Available",
        "Not Specified",
        "OEM",
        "System Serial Number",
    )
    _version_blacklist = (
        "-1",
        "<BAD INDEX>",
        "N/A",
        "None",
        "Not Applicable",
        "Not Available",
        "Not Specified",
        "OEM",
        "System Version",
        "Unknown",
        "x.x",
    )

    def __init__(self, attributes, category):
        self._attributes = attributes
        self.category = category

    @property
    def path(self):
        path = "/devices/virtual/dmi/id"
        return os.path.join(path, self.category.lower())

    @property
    def product(self):
        if self.category == "CHASSIS":
            type_string = self._attributes.get("chassis_type", "0")
            try:
                type_index = int(type_string)
            except ValueError:
                return type_string
            if 0 <= type_index < len(Dmi.chassis_types):
                return Dmi.chassis_types[type_index]
            return "Unknown"

        for name in "name", "version":
            attribute = "%s_%s" % (self.category.lower(), name)
            product = self._attributes.get(attribute)
            if product and product not in self._product_blacklist:
                return product

        return None

    @property
    def vendor(self):
        for name in "manufacturer", "vendor":
            attribute = "%s_%s" % (self.category.lower(), name)
            vendor = self._attributes.get(attribute)
            if vendor and vendor not in self._vendor_blacklist:
                return vendor

        return None

    @property
    def serial(self):
        attribute = "%s_serial" % self.category.lower()
        serial = self._attributes.get(attribute)
        if serial and serial not in self._serial_blacklist:
            return serial

        return None

    @property
    def version(self):
        attribute = "%s_version" % self.category.lower()
        version = self._attributes.get(attribute)
        if version and version not in self._version_blacklist:
            return version

        return None

    @property
    def size(self):
        attribute = "%s_size" % self.category.lower()
        size = self._attributes.get(attribute)

        if size:
            size = string_to_type(size)

        return size

    @property
    def form(self):
        attribute = "%s_form" % self.category.lower()
        return self._attributes.get(attribute)

    @property
    def sku(self):
        attribute = "%s_sku" % self.category.lower()
        return self._attributes.get(attribute)

    @property
    def raw_attributes(self):
        """
        Access "raw" non-collapsed DMI data.

        The well-known accessor methods allow direct access
        to the essential and usually-always-present DMI
        attributes. But to access other less-known, custom
        attributes, raw_attribute can be used.

        DMI keys, or field names/identifiers, are converted
        to lowercase, spaces are replaced with underscores,
        and they're stored as-is in the _attributes dictionary.

        Returns a dictionary with each data item from self._attributes
        but with the prefix ("self.category.lower()_") removed.
        """
        # Note a dict comprehension is not used out of fear of python 2.x.
        return dict(
            [
                (k.replace("%s_" % self.category.lower(), "", 1), v)
                for k, v in self._attributes.items()
            ]
        )
