# This file is part of Checkbox.
#
# Copyright 2020-2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
This module provides information about USB devices available in the system
based on the data available in sysfs.
"""
import contextlib
import glob
import os
import re
import string

from collections import OrderedDict
from enum import Enum
from functools import partial


def ishex(chars):
    """Checks if all `chars` are hexdigits [0-9a-f]."""
    return all([x in string.hexdigits for x in chars])


class UsbIds:
    """USB IDs database reference."""

    def decode_vendor(self, vid):
        """Translate vendor ID to a Vendor Name."""
        return self._vendors[vid]

    def decode_product(self, vid, pid):
        """Transate vendor ID and product ID to a device name."""
        return '{} {}'.format(
            self._vendors[vid], self._products[vid, pid])

    def decode_protocol(self, cid, scid, prid):
        """
        Translate interface class protocol from IDs to a human-readable name.

        There is a cascade of fallbacks if some of the more IDs is not known.
        See implementation for details.
        """
        return (
            self._protocols.get((cid, scid, prid)) or
            self._subclasses.get((cid, scid)) or
            self._classes.get(cid) or
            ''
        )

    def __init__(self, usb_ids_path=None):
        self._vendors = OrderedDict()
        self._products = OrderedDict()
        self._classes = OrderedDict()
        self._subclasses = OrderedDict()
        self._protocols = OrderedDict()
        if usb_ids_path:
            paths = [usb_ids_path]
        else:
            paths = [
                # focal, bionic, xenial, and debian(s)
                '/var/lib/usbutils/usb.ids',
                # fallback - used in kernel maintainer's repos
                '/usr/share/usb.ids',
            ]
        for path in paths:
            if os.path.isfile(path):
                # at the time of writing this the usb_ids has one line that
                # uses character from beyond standard ascii 7-bit set. namely
                # 0xb4 (Accent Acute). I couldn't find information about the
                # file's encoding, but iso match it nicely.  The other way to
                # cover for those cases would be to use surrogates and then
                # have some pass to interpret them.
                with open(path, 'rt', encoding='iso8859') as usb_ids_file:
                    self._parse_usb_ids(usb_ids_file.read())

    def _parse_usb_ids(self, content):
        """Parse the contents of usb.ids file."""

        class ParserContext(Enum):
            """Context marker for usb.ids parser."""
            DEFAULT = 0
            VENDOR = 1
            CLASS = 2
            OTHER = 3

        context = ParserContext.DEFAULT

        for line in content.splitlines():
            if not line or line[0] == '#':
                # empty line or a comment
                continue
            if ishex(line[:4]):
                # vendor information
                vid = int(line[:4], 16)
                self._vendors[vid] = line[6:]
                context = ParserContext.VENDOR
                continue
            if line[0] == '\t' and ishex(line[1:3]):
                # classes use only 2 hex digits, devices use 4
                if context == ParserContext.VENDOR:
                    pid = int(line[1:5], 16)
                    # last added vendor is the current vendor
                    vid = list(self._vendors.keys())[-1]
                    self._products[vid, pid] = line[7:]
                    continue
                if context == ParserContext.CLASS:
                    subclass_id = int(line[1:5], 16)
                    name = line[5:]
                    class_id = list(self._classes.keys())[-1]
                    description = "{}:{}".format(
                        self._classes[class_id],
                        name if name != 'Unused' else '')
                    self._subclasses[class_id, subclass_id] = description
                    continue
            if line[0] == 'C':
                context = ParserContext.CLASS
                class_id = int(line[2:4], 16)
                class_name = line[6:]
                self._classes[class_id] = class_name
                continue
            if line[0:2] == '\t\t' and ishex(line[2:4]):
                protocol_id = int(line[2:4], 16)
                class_id, subclass_id = list(self._subclasses.keys())[-1]
                description = "{}:{}".format(
                    self._subclasses[class_id, subclass_id], line[6:])
                self._protocols[class_id, subclass_id, protocol_id] = (
                    description)
                continue
            # if we got here without satisfying any of the above ifs
            # then we need to set paraser into a state where lines won't be
            # consumed
            context = ParserContext.OTHER


def read_entry(sysfs_path, field):
    """Read a sysfs attribute."""
    with open(os.path.join(sysfs_path, field), 'rt') as fentry:
        return fentry.readline().strip('\n')


class UsbInterface(dict):
    """
    A proxy to sysfs entry for a USB Interface.
    """
    def __init__(self, sysfs_path, usb_ids, parent):
        super().__init__(self)
        self.sysfs_path = sysfs_path
        self.address = os.path.basename(self.sysfs_path)
        self._parent = parent
        self._level = 0
        while parent:
            self._level += 1
            parent = parent.parent
        hex_int_fields = [
            'bInterfaceClass', 'bInterfaceSubClass', 'bInterfaceProtocol']
        for field in hex_int_fields:
            self[field] = int(read_entry(sysfs_path, field), 16)
        self['bNumEndpoints'] = int(read_entry(sysfs_path, 'bNumEndpoints'))
        self['driver'] = ''
        self['name'] = ''
        with contextlib.suppress(Exception):
            self['driver'] = os.path.basename(
                os.readlink(os.path.join(sysfs_path, 'driver')))
        self['protocol_name'] = usb_ids.decode_protocol(
            self['bInterfaceClass'], self['bInterfaceSubClass'],
            self['bInterfaceProtocol'])

    def to_str(self):
        """Generate a string representation of this Interface."""
        template = (
            '{padded_name:16}(IF) {bInterfaceClass:02x}:'
            '{bInterfaceSubClass:02x}:{bInterfaceProtocol:02x} '
            '{bNumEndpoints}EPs ({protocol_name}) {driver} {name}'
        )
        padded_name = ' ' * self._level + self.address
        half_done = partial(template.format, padded_name=padded_name)
        line = half_done(**self)
        return line

    def __hash__(self):
        return hash(frozenset(self.items()))


class UsbDevice(dict):
    """
    A proxy to sysfs entry for a device.

    Attributes can be read as dictionary keys.
    Sub-devices are available from the `children` property.
    """
    def __init__(self, sysfs_path, usb_ids, parent=None):
        super().__init__(self)
        self.sysfs_path = sysfs_path
        self.address = os.path.basename(self.sysfs_path)
        self.parent = parent
        self._level = 0
        while parent:
            self._level += 1
            parent = parent.parent
        self.children = []
        self.interfaces = []
        hex_int_fields = [
            'bDeviceClass', 'bDeviceSubClass', 'bDeviceProtocol',
            'idVendor', 'idProduct',
        ]
        for field in hex_int_fields:
            self[field] = int(read_entry(sysfs_path, field), 16)
        int_fields = ['maxchild', 'bNumInterfaces', 'busnum', 'devnum']
        for field in int_fields:
            self[field] = int(read_entry(sysfs_path, field))
        str_fields = ['version', 'speed', 'bMaxPower']
        for field in str_fields:
            self[field] = read_entry(sysfs_path, field)
        # let's try getting the name directly from sysfs entries
        self['name'] = ''
        with contextlib.suppress(Exception):
            # any of the next three attributes may be missing, so let's try
            # going one by one. If an exception is raised while getting any
            # part the previous parts will be already stored in self['name']
            self['name'] = read_entry(sysfs_path, 'manufacturer')
            self['name'] += ' ' + read_entry(sysfs_path, 'product')
            self['name'] += ' ' + read_entry(sysfs_path, 'serial')
        # for HCI host controller entry we may want to trim the name bit
        if self['name'].startswith('Linux'):
            regex = r"Linux [^ ]* .hci[-_]hcd"
            if re.search(regex, self['name']):
                self['name'] = "Linux Foundation {:.2f} root hub".format(
                    float(self['version']))
        # if nothing got read from sysfs we need to consult the USB IDS DB
        if not self['name']:
            with contextlib.suppress(Exception):
                self['name'] = usb_ids.decode_product(
                    self['idVendor'], self['idProduct'])
        if not self['name']:
            # last change, try just the vendor name
            with contextlib.suppress(Exception):
                self['name'] = usb_ids.decode_vendor(self['idVendor'])
    # now onto children, some of them are real usb devices, and some are just
    # interfaces that the current device implements
        for node in os.listdir(sysfs_path):
            if not node[0].isdigit():
                continue
            sub_path = os.path.join(sysfs_path, node)
            if os.path.exists(os.path.join(sub_path, 'bInterfaceClass')):
                # interface information
                self.interfaces.append(UsbInterface(sub_path, usb_ids, self))
            else:
                # 'real' USB device
                self.children.append(UsbDevice(sub_path, usb_ids, self))

    def to_str(self):
        """Generate a string representation of this USB Device."""
        template = (
            '{padded_name:16}{idVendor:04x}:{idProduct:04x} '
            '{bDeviceClass:02x} {version} {speed:3}MBit/s {bMaxPower} '
            '{bNumInterfaces}IFs ({name})'
        )
        padded_name = ' ' * self._level + self.address
        half_done = partial(template.format, padded_name=padded_name)
        line = half_done(**self)
        children_strs = [c.to_str() for c in self.children]
        ifaces_strs = [i.to_str() for i in self.interfaces]
        return '\n'.join([line] + children_strs + ifaces_strs)

    def to_short_str(self):
        """Generate a short string representation of this USB Device."""
        template = 'ID {idVendor:04x}:{idProduct:04x} {name}'
        return '\n'.join([template.format(**self)] + [
            c.to_short_str() for c in self.children])

    def to_legacy_str(self):
        """
        Generate a string representation similar to early versions of lsusb.py
        written for python2.
        """
        template = (
            'Bus {busnum:03} Device {devnum:03} '
            'ID {idVendor:04x}:{idProduct:04x} {name}'
        )
        return '\n'.join([template.format(**self)] + [
            c.to_legacy_str() for c in self.children])

    def get_all_devices(self):
        """Return a flat list of USB devices (this one + children)."""
        return [self] + self.children + self.interfaces

    def __hash__(self):
        return hash(frozenset(self.items()))


def get_root_devices(usb_ids=None):
    """
    Get dict-like objects representing USB devices.

    `usb_ids` argument should be an instance to UsbIds object. If not supplied
    one with default settings will be created.
    """
    usb_ids = usb_ids or UsbIds()
    for node in glob.glob("/sys/bus/usb/devices/usb*"):
        yield UsbDevice(node, usb_ids)


def get_all_usb_devices():
    """Get all USB devices available in the system."""
    roots = get_root_devices()
    for root in roots:
        for dev in root.get_all_devices():
            yield dev
