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

import argparse
import fcntl
import os
import socket
import struct
from subprocess import check_output, CalledProcessError, STDOUT
import sys

import dbus

from checkbox_support.parsers.modinfo import ModinfoParser
from checkbox_support.parsers.udevadm import UdevadmParser


class Utils():

    sys_path = '/sys/class/net'

    @classmethod
    def is_iface_connected(cls, iface):
        try:
            carrier_file = os.path.join(cls.sys_path, iface, 'carrier')
            return int(open(carrier_file, 'r').read()) == 1
        except Exception:
            pass
        return False

    @staticmethod
    def get_ipv4_address(interface):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            ipv4_addr = socket.inet_ntoa(fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', interface[:15].encode())
            )[20:24])
        except Exception as e:
            print("ERROR: getting the IPv4 address for %s: %s" %
                  (interface, repr(e)))
            ipv4_addr = "***NOT CONFIGURED***"
        finally:
            return ipv4_addr

    @staticmethod
    def get_ipv6_address(interface):
        cmd = ['/sbin/ip', '-6', '-o', 'addr', 'show', 'dev', interface,
               'scope', 'link']
        proc = check_output(cmd, universal_newlines=True)
        return proc.split()[3].strip()

    @classmethod
    def get_mac_address(cls, interface):
        address_file = os.path.join(cls.sys_path, interface, 'address')
        try:
            return open(address_file, 'r').read().strip()
        except IOError:
            return 'UNKNOWN'

    @classmethod
    def get_speed(cls, interface):
        speed_file = os.path.join(cls.sys_path, interface, 'speed')
        try:
            return open(speed_file, 'r').read().strip()
        except IOError:
            return 'UNKNOWN'

    @staticmethod
    def get_driver_version(driver):
        cmd = ['/sbin/modinfo', driver]
        try:
            output = check_output(cmd, stderr=STDOUT, universal_newlines=True)
        except CalledProcessError:
            return None
        if not output:
            return None
        parser = ModinfoParser(output)
        modinfo = parser.get_all()

        # try the version field first, then vermagic second, some audio
        # drivers don't report version if the driver is in-tree
        version = modinfo.get('version')

        if version is None or version == 'in-tree':
            # vermagic will look like this (below) and we only care about the
            # first part:
            # "3.2.0-29-generic SMP mod_unload modversions"
            version = modinfo.get('vermagic').split()[0]

        return version


class NetworkDeviceInfo():

    def __init__(self):
        self._category = None
        self._interface = None
        self._product = None
        self._vendor = None
        self._driver = None
        self._driver_version = None
        self._firmware_missing = None
        self._path = None
        self._id = None
        self._subsystem_id = None
        self._mac = None
        self._carrier_status = None
        self._ipv4 = None
        self._ipv6 = None
        self._speed = None

    def __str__(self):
        ret = ""
        for key, val in vars(self).items():
            if val is not None:
                # leading _ removed, remaining ones spaces
                pretty_key = key.lstrip('_').replace('_', ' ').title()
                ret += '{}: {}\n'.format(pretty_key, val)
        return ret

    @property
    def interface(self):
        return self._interface

    @interface.setter
    def interface(self, value):
        self._interface = value
        self._interface_populate()

    @property
    def carrier_status(self):
        return self._carrier_status

    @property
    def driver(self):
        return self._driver

    @driver.setter
    def driver(self, value):
        self._driver = value
        self._driver_populate()

    @property
    def category(self):
        return self._category

    @category.setter
    def category(self, value):
        self._category = value

    @property
    def product(self):
        return self._product

    @product.setter
    def product(self, value):
        self._product = value

    @property
    def vendor(self):
        return self._vendor

    @vendor.setter
    def vendor(self, value):
        self._vendor = value

    @property
    def firmware_missing(self):
        return self._firmware_missing

    @firmware_missing.setter
    def firmware_missing(self, value):
        self._firmware_missing = value

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        self._path = value

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def subsystem_id(self):
        return self._subsystem_id

    @subsystem_id.setter
    def subsystem_id(self, value):
        self._subsystem_id = value

    def _interface_populate(self):
        """Get extra attributes based on interface"""
        if self.interface is None:
            return
        self._mac = Utils.get_mac_address(self.interface)
        if Utils.is_iface_connected(self.interface):
            self._carrier_status = 'Connected'
            self._ipv4 = Utils.get_ipv4_address(self.interface)
            self._ipv6 = Utils.get_ipv6_address(self.interface)
            self._speed = Utils.get_speed(self.interface)
        else:
            self._carrier_status = 'Disconnected'

    def _driver_populate(self):
        """Get extra attributes based on driver"""
        if self.driver is None:
            return
        self._driver_version = Utils.get_driver_version(self.driver)


class NMDevices():

    # This example lists basic information about network interfaces known to NM
    devtypes = {1: "Ethernet",
                2: "WiFi",
                5: "Bluetooth",
                6: "OLPC",
                7: "WiMAX",
                8: "Modem"}

    def __init__(self, category="NETWORK"):
        self.category = category
        self._devices = []
        self._collect_devices()

    def __len__(self):
        return len(self._devices)

    def _collect_devices(self):
        bus = dbus.SystemBus()
        proxy = bus.get_object("org.freedesktop.NetworkManager",
                               "/org/freedesktop/NetworkManager")
        manager = dbus.Interface(proxy, "org.freedesktop.NetworkManager")
        self._devices = manager.GetDevices()

    def devices(self):
        """Convert to list of NetworkDevice with NM derived attrs set"""
        for d in self._devices:
            bus = dbus.SystemBus()
            dev_proxy = bus.get_object("org.freedesktop.NetworkManager", d)
            prop_iface = dbus.Interface(dev_proxy,
                                        "org.freedesktop.DBus.Properties")
            props = prop_iface.GetAll("org.freedesktop.NetworkManager.Device")
            devtype = self.devtypes.get(props.get('DeviceType'))
            if devtype is None:
                continue
            nd = NetworkDeviceInfo()
            if self.category == "NETWORK":
                if devtype == "Ethernet":
                    nd.category = self.category
                else:
                    continue
            if self.category == "WIRELESS":
                if devtype == "WiFi":
                    nd.category = self.category
                else:
                    continue
            nd.interface = props.get('Interface')
            nd.driver = props.get('Driver')
            nd.firmware_missing = props.get('FirmwareMissing')
            yield nd


class UdevDevices():

    def __init__(self, category='NETWORK'):
        self.category = category
        self._devices = []
        self._collect_devices()

    def __len__(self):
        return len(self._devices)

    def _collect_devices(self):
        cmd = ['udevadm', 'info', '--export-db']
        try:
            output = check_output(cmd).decode(sys.stdout.encoding)
        except CalledProcessError as err:
            sys.stderr.write(err)
            return
        udev = UdevadmParser(output)
        for device in udev.run():
            if (device.category == self.category and
                    device.interface != 'UNKNOWN'):
                self._devices.append(device)

    def devices(self):
        """Convert to list of NetworkDevice with UDev derived attrs set"""
        for device in self._devices:
            nd = NetworkDeviceInfo()
            nd.category = getattr(device, 'category', None)
            nd.interface = getattr(device, 'interface', None)
            nd.product = getattr(device, 'product', None)
            nd.vendor = getattr(device, 'vendor', None)
            nd.driver = getattr(device, 'driver', None)
            nd.path = getattr(device, 'path', None)
            vid = getattr(device, 'vendor_id', None)
            pid = getattr(device, 'product_id', None)
            if vid and pid:
                nd.id = '[{0:04x}:{1:04x}]'.format(vid, pid)
            svid = getattr(device, 'subvendor_id', None)
            spid = getattr(device, 'subproduct_id', None)
            if svid and spid:
                nd.subsystem_id = '[{0:04x}:{1:04x}]'.format(svid, spid)
            yield nd


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Gather information about network devices')
    parser.add_argument('action', choices=('detect', 'info'),
                        help='Detect mode or just report info')
    parser.add_argument('category', choices=('NETWORK', 'WIRELESS'),
                        help='Either ethernet or WLAN devices')
    parser.add_argument('--no-nm', action='store_true',
                        help='Don\'t attempt to get info from network manager')
    parser.add_argument('--interface',
                        help='Restrict info action to specified interface')
    parser.add_argument('--fail-on-disconnected', action='store_true',
                        help=('Script will exit with a non-zero return code if'
                              ' any interface is not connected'))
    args = parser.parse_args()

    udev = UdevDevices(args.category)
    disconnected_ifaces = []

    # The detect action should indicate presence of a device belonging to the
    # category and cause the job to fail if none present
    if args.action == 'detect':
        if len(udev) == 0:
            raise SystemExit('No devices detected by udev')
        else:
            print("[ Devices found by udev ]".center(80, '-'))
            for device in udev.devices():
                print(device)

    # The info action should just gather infomation about any ethernet devices
    # found and report for inclusion in e.g. an attachment job and include
    # NetworkManager as a source if desired
    if args.action == 'info':
        # If interface has been specified
        if args.interface:
            for device in udev.devices():
                if device.interface == args.interface:
                    print(device)
            sys.exit(0)

        # Report udev detected devices first
        print("[ Devices found by udev ]".center(80, '-'))
        for device in udev.devices():
            print(device)
            if device.carrier_status == "Disconnected":
                disconnected_ifaces.append(device.interface)

        # Attempt to report devices found by NetworkManager. This can be
        # skipped as doesn't make sense for server installs
        if not args.no_nm:
            nm = NMDevices(args.category)
            print("[ Devices found by Network Manager ]".center(80, '-'))
            for device in nm.devices():
                print(device)

        if disconnected_ifaces and args.fail_on_disconnected:
            print("WARNING: The following interfaces are not connected:")
            for iface in disconnected_ifaces:
                print(iface)
            sys.exit(1)

    sys.exit(0)
