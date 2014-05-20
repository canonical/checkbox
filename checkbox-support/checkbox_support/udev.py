# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
checkbox_support.udev
=====================

A collection of utility functions for interacting with GUdev
"""

from gi.repository import GUdev

from checkbox_support.heuristics.udev import is_virtual_device


def get_interconnect_speed(device):
    """
    Compute the speed of the USB interconnect of single device

    This function traverses up the tree of devices all the way to the root
    object and returns the minimum value of the 'speed' sysfs attribute, or
    None if there was no speed in any of the devices.
    """
    # We'll track the actual speed of the interconnect here. The value None
    # means that we just don't know
    interconnect_speed = None
    while device:
        # For each udev device that we traverse we attempt to lookup the
        # 'speed' attribute. If present it is converted to an ASCII string and
        # then to an integer. That integer represents the speed of the
        # interconnect in megabits.
        #
        # Here we use get_sysfs_attr_as_int that does it all for us, returning
        # 0 if anything is wrong.
        device_speed = device.get_sysfs_attr_as_int('speed')
        if device_speed != 0:  # Empty values get truncated to 0
            # As USB devices can be connected via any number of hubs we
            # carefully use the smallest number that is encountered but it
            # seems that the Kernel already does the right thing and shows a
            # SuperSpeed USB 3.0 device (that normally has speed of 5000Mbit/s)
            # which is connected to a HighSpeed USB 2.0 device (that is limited
            # to 480Mbit/s) to also have the smaller, 480Mbit/s speed.
            if interconnect_speed is not None:
                interconnect_speed = min(interconnect_speed, device_speed)
            else:
                interconnect_speed = device_speed
        # We walk up the tree of udev devices looking for any parent that
        # belongs to the 'usb' subsystem having device_type of 'usb_device'. I
        # have not managed to find any documentation about this (I've yet to
        # check Kernel documentation) but casual observation and testing seems
        # to indicate that this is what we want.
        # TODO: get_parent_with_subsystem('usb', 'usb_device')
        device = device.get_parent()
    return interconnect_speed


def get_udev_block_devices(udev_client):
    """
    Get a list of all block devices

    Returns a list of GUdev.Device objects representing all block devices in
    the system. Virtual devices are filtered away using
    checkbox_support.heuristics.udev.is_virtual_device.
    """
    # setup an enumerator so that we can list devices
    enumerator = GUdev.Enumerator(client=udev_client)
    # Iterate over block devices only
    enumerator.add_match_subsystem('block')
    # Convert the enumerator into a plain list and filter-away all
    # devices deemed virtual by the heuristic.
    devices = [
        device for device in enumerator.execute()
        if not is_virtual_device(device.get_device_file())]
    # Sort the list, this is not needed but makes various debugging dumps
    # look better.
    devices.sort(key=lambda device: device.get_device_file())
    return devices


def get_udev_xhci_devices(udev_client):
    """
    Get a list of all devices on pci slots using xhci drivers
    """
    # setup an enumerator so that we can list devices
    enumerator = GUdev.Enumerator(client=udev_client)
    # Iterate over pci devices only
    enumerator.add_match_subsystem('pci')
    devices = [
        device for device in enumerator.execute()
        if (device.get_driver() == 'xhci_hcd')]
    # Sort the list, this is not needed but makes various debugging dumps
    # look better.
    devices.sort(key=lambda device: device.get_property('PCI_SLOT_NAME'))
    return devices
