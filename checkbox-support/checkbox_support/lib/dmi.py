#
# This file is part of Checkbox.
#
# Copyright 2008 Canonical Ltd.
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
import os

from checkbox.lib.conversion import string_to_type

# See also 3.3.4.1 of the "System Management BIOS Reference Specification,
# Version 2.6.1" (Preliminary Standard) document, available from
# http://www.dmtf.org/standards/smbios.
class Dmi:
    chassis = (
        ("Undefined",             "unknown"),  # 0x00
        ("Other",                 "unknown"),
        ("Unknown",               "unknown"),
        ("Desktop",               "desktop"),
        ("Low Profile Desktop",   "desktop"),
        ("Pizza Box",             "server"),
        ("Mini Tower",            "desktop"),
        ("Tower",                 "desktop"),
        ("Portable",              "laptop"),
        ("Laptop",                "laptop"),
        ("Notebook",              "laptop"),
        ("Hand Held",             "handheld"),
        ("Docking Station",       "laptop"),
        ("All In One",            "unknown"),
        ("Sub Notebook",          "laptop"),
        ("Space-saving",          "desktop"),
        ("Lunch Box",             "unknown"),
        ("Main Server Chassis",   "server"),
        ("Expansion Chassis",     "unknown"),
        ("Sub Chassis",           "unknown"),
        ("Bus Expansion Chassis", "unknown"),
        ("Peripheral Chassis",    "unknown"),
        ("RAID Chassis",          "unknown"),
        ("Rack Mount Chassis",    "unknown"),
        ("Sealed-case PC",        "unknown"),
        ("Multi-system",          "unknown"),
        ("CompactPCI",            "unknonw"),
        ("AdvancedTCA",           "unknown"),
        ("Blade",                 "server"),
        ("Blade Enclosure",       "unknown"))

    chassis_names = tuple(c[0] for c in chassis)
    chassis_types = tuple(c[1] for c in chassis)
    chassis_name_to_type = dict(chassis)

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
                return Dmi.chassis_names[type_index]
            except ValueError:
                return type_string

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
