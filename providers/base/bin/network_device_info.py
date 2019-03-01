#!/usr/bin/env python3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Parts of this are based on the example python code that ships with
# NetworkManager
# http://cgit.freedesktop.org/NetworkManager/NetworkManager/tree/examples/python
#
# Copyright (C) 2012-2019 Canonical, Ltd.

from subprocess import check_output, CalledProcessError, STDOUT
import sys

import dbus

from checkbox_support.parsers.modinfo import ModinfoParser
from checkbox_support.parsers.udevadm import UdevadmParser


# This example lists basic information about network interfaces known to NM
devtypes = {1: "Ethernet",
            2: "WiFi",
            5: "Bluetooth",
            6: "OLPC",
            7: "WiMAX",
            8: "Modem"}

states = {0: "Unknown",
          10: "Unmanaged",
          20: "Unavailable",
          30: "Disconnected",
          40: "Prepare",
          50: "Config",
          60: "Need Auth",
          70: "IP Config",
          80: "IP Check",
          90: "Secondaries",
          100: "Activated",
          110: "Deactivating",
          120: "Failed"}

attributes = ("category", "interface", "product", "vendor", "driver", "path")

udev_devices = []
nm_devices = []


class UdevResult:
    def addDevice(self, device):
        if device.category == 'NETWORK' and device.interface != "UNKNOWN":
            udev_devices.append(device)


class NetworkingDevice():
    def __init__(self, devtype, props, dev_proxy, bus):
        self._devtype = devtype
        try:
            self._interface = props['Interface']
        except KeyError:
            self._interface = "Unknown"

        try:
            self._ip = self._int_to_ip(props['Ip4Address'])
        except KeyError:
            self._ip = "Unknown"

        try:
            self._driver = props['Driver']
        except KeyError:
            self._driver = "Unknown"
            self._driver_ver = "Unknown"

        if self._driver != "Unknown":
            self._modinfo = self._modinfo_parser(props['Driver'])
            if self._modinfo:
                self._driver_ver = self._find_driver_ver()
            else:
                self._driver_ver = "Unknown"

        try:
            self._firmware_missing = props['FirmwareMissing']
        except KeyError:
            self._firmware_missing = False

        try:
            self._state = states[props['State']]
        except KeyError:
            self._state = "Unknown"

    def __str__(self):
        ret = "Category: %s\n" % self._devtype
        ret += "Interface: %s\n" % self._interface
        ret += "IP: %s\n" % self._ip
        ret += "Driver: %s (ver: %s)\n" % (self._driver, self._driver_ver)
        if self._firmware_missing:
            ret += "Warning: Required Firmware Missing for device\n"
        ret += "State: %s\n" % self._state
        return ret

    def getstate(self):
        return self._state

    def gettype(self):
        return self._devtype

    def _bitrate_to_mbps(self, bitrate):
        try:
            intbr = int(bitrate)
            return str(intbr / 1000)
        except Exception:
            return "NaN"

    def _modinfo_parser(self, driver):
        cmd = ['/sbin/modinfo', driver]
        try:
            stream = check_output(cmd, stderr=STDOUT, universal_newlines=True)
        except CalledProcessError:
            return None

        if not stream:
            return None
        else:
            parser = ModinfoParser(stream)
            modinfo = parser.get_all()

        return modinfo

    def _find_driver_ver(self):
        # try the version field first, then vermagic second, some audio
        # drivers don't report version if the driver is in-tree
        if self._modinfo['version'] and self._modinfo['version'] != 'in-tree:':
            return self._modinfo['version']
        else:
            # vermagic will look like this (below) and we only care about the
            # first part:
            # "3.2.0-29-generic SMP mod_unload modversions"
            return self._modinfo['vermagic'].split()[0]

    def _int_to_ip(self, int_ip):
        ip = [0, 0, 0, 0]
        ip[0] = int_ip & 0xff
        ip[1] = (int_ip >> 8) & 0xff
        ip[2] = (int_ip >> 16) & 0xff
        ip[3] = (int_ip >> 24) & 0xff
        return "%d.%d.%d.%d" % (ip[0], ip[1], ip[2], ip[3])


def print_udev_devices():
    print("[ Devices found by udev ]".center(80, '-'))
    for device in udev_devices:
        for attribute in attributes:
            value = getattr(device, attribute)
            if value is not None:
                if attribute == 'driver':
                    props = {}
                    props['Driver'] = value
                    network_dev = NetworkingDevice(
                        None, props, None, None)
                    print("%s: %s (ver: %s)" % (
                        attribute.capitalize(), value,
                        network_dev._driver_ver))
                else:
                    print("%s: %s" % (attribute.capitalize(), value))
        vendor_id = getattr(device, 'vendor_id')
        product_id = getattr(device, 'product_id')
        subvendor_id = getattr(device, 'subvendor_id')
        subproduct_id = getattr(device, 'subproduct_id')
        if vendor_id and product_id:
            print("ID:           [{0:04x}:{1:04x}]".format(
                vendor_id, product_id))
        if subvendor_id and subproduct_id:
            print("Subsystem ID: [{0:04x}:{1:04x}]".format(
                subvendor_id, subproduct_id))
        print()


def get_nm_devices():
    devices = []
    bus = dbus.SystemBus()

    # Get a proxy for the base NetworkManager object
    proxy = bus.get_object("org.freedesktop.NetworkManager",
                           "/org/freedesktop/NetworkManager")
    manager = dbus.Interface(proxy, "org.freedesktop.NetworkManager")

    # Get all devices known to NM and print their properties
    nm_devices = manager.GetDevices()
    for d in nm_devices:
        dev_proxy = bus.get_object("org.freedesktop.NetworkManager", d)
        prop_iface = dbus.Interface(dev_proxy,
                                    "org.freedesktop.DBus.Properties")
        props = prop_iface.GetAll("org.freedesktop.NetworkManager.Device")
        try:
            devtype = devtypes[props['DeviceType']]
        except KeyError:
            devtype = "Unknown"

        # only return Ethernet devices
        if devtype == "Ethernet":
            devices.append(NetworkingDevice(devtype, props, dev_proxy, bus))
    return devices


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('detect', 'info'):
        raise SystemExit('ERROR: please specify detect or info')
    action = sys.argv[1]

    try:
        output = check_output(['udevadm', 'info', '--export-db'])
    except CalledProcessError as err:
        raise SystemExit(err)
    try:
        output = output.decode("UTF-8", errors='ignore')
    except UnicodeDecodeError as err:
        raise SystemExit("udevadm output is not valid UTF-8")
    udev = UdevadmParser(output)
    result = UdevResult()
    udev.run(result)

    # The detect action should indicate presence of an ethernet adatper and
    # cause the job to fail if none present - rely on udev for this
    if action == 'detect':
        if udev_devices:
            print_udev_devices()
        else:
            raise SystemExit('No devices detected by udev')

    # The info action should just gather infomation about any ethernet devices
    # found and report for inclusion in e.g. an attachment job
    if action == 'info':
        # Report udev detected devices first
        if udev_devices:
            print_udev_devices()

        # Attempt to report devices found by NetworkManager - this doesn't
        # make sense for server installs so skipping is acceptable
        try:
            nm_devices = get_nm_devices()
        except dbus.exceptions.DBusException:
            # server's don't have network manager installed
            print('Network Manager not found')
        else:
            print("[ Devices found by Network Manager ]".center(80, '-'))
            for nm_dev in nm_devices:
                print(nm_dev)


if __name__ == "__main__":
    main()
