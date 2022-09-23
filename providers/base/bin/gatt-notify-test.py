#!/usr/bin/env python3
#
# Copyright 2018 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import logging
import os
import sys
import time

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GObject

logger = logging.getLogger(__file__)
logger.addHandler(logging.StreamHandler(sys.stdout))

ADAPTER_INTERFACE = 'org.bluez.Adapter1'
DEVICE_INTERFACE = 'org.bluez.Device1'
PROP_INTERFACE = 'org.freedesktop.DBus.Properties'
OM_INTERFACE = 'org.freedesktop.DBus.ObjectManager'
GATT_SERVICE_INTERFACE = 'org.bluez.GattService1'
GATT_CHRC_INTERFACE = 'org.bluez.GattCharacteristic1'

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class BtAdapter:
    """Bluetooth LE Adapter class."""
    def __init__(self, pattern):
        self._pattern = os.path.basename(pattern)
        self._bus = dbus.SystemBus()
        self._manager = dbus.Interface(
            self._bus.get_object("org.bluez", "/"), OM_INTERFACE)
        self._main_loop = GObject.MainLoop()
        self._adapter = self._find_adapter()
        self._path = self._adapter.object_path
        self._props = dbus.Interface(self._adapter, PROP_INTERFACE)
        self._name = self._props.Get(ADAPTER_INTERFACE, "Name")
        self._addr = self._props.Get(ADAPTER_INTERFACE, "Address")
        self._alias = self._props.Get(ADAPTER_INTERFACE, "Alias")
        logger.info('Adapter found: [ {} ] {} - {}'.format(
            self._path, self._addr, self._alias))

    def _get_managed_objects(self):
        return self._manager.GetManagedObjects()

    def _find_adapter(self):
        for path, ifaces in self._get_managed_objects().items():
            adapter = ifaces.get(ADAPTER_INTERFACE)
            if adapter is None:
                continue
            if (self._pattern == adapter["Address"] or
                    path.endswith(self._pattern)):
                obj = self._bus.get_object("org.bluez", path)
                return dbus.Interface(obj, ADAPTER_INTERFACE)
        raise SystemExit("Bluetooth adapter not found!")

    def ensure_powered(self):
        """Turn the adapter on."""
        self._props.Set(ADAPTER_INTERFACE, "Powered", dbus.Boolean(1))
        logger.info('Adapter powered on')

    def scan(self, timeout=10):
        """Scan for BT devices."""
        dbus.Interface(self._adapter, ADAPTER_INTERFACE).StartDiscovery()
        logger.info('Adapter scan on ({}s)'.format(timeout))
        GObject.timeout_add_seconds(timeout, self._scan_timeout)
        self._main_loop.run()

    def _scan_timeout(self):
        dbus.Interface(self._adapter, ADAPTER_INTERFACE).StopDiscovery()
        logger.info('Adapter scan completed')
        self._main_loop.quit()

    def find_device_with_service(self, ADV_SVC_UUID):
        """Find a device with a given remote service."""
        for path, ifaces in self._get_managed_objects().items():
            device = ifaces.get(DEVICE_INTERFACE)
            if device is None:
                continue
            logger.debug("{} {} {}".format(
                path, device["Address"], device["Alias"]))
            if ADV_SVC_UUID in device["UUIDs"] and path.startswith(self._path):
                obj = self._bus.get_object("org.bluez", path)
                logger.info('Device found: [ {} ] {} - {}'.format(
                    path, device["Name"], device["Address"]))
                return dbus.Interface(obj, DEVICE_INTERFACE)
        raise SystemExit("Bluetooth device not found!")

    def remove_device(self, device):
        """Remove the remote device object at the given path."""
        try:
            self._adapter.RemoveDevice(device)
        except dbus.exceptions.DBusException as msg:
            logging.error(msg)
            raise SystemExit(1)
        logger.info('Device properly removed')


class BtGATTRemoteService:
    """Bluetooth LE GATT Remote Service class."""
    def __init__(self, SVC_UUID, adapter, device, max_notif):
        self.SVC_UUID = SVC_UUID
        self._adapter = adapter
        self.device = device
        self._max_notif = max_notif
        self._notifications = 0
        self._bus = dbus.SystemBus()
        self._manager = dbus.Interface(
            self._bus.get_object("org.bluez", "/"), OM_INTERFACE)
        self._main_loop = GObject.MainLoop()
        self._service = self._find_service()
        self._path = self._service.object_path

    def _get_managed_objects(self):
        return self._manager.GetManagedObjects()

    def _find_service(self):
        for path, ifaces in self._get_managed_objects().items():
            if GATT_SERVICE_INTERFACE not in ifaces.keys():
                continue
            service = self._bus.get_object('org.bluez', path)
            props = dbus.Interface(service, PROP_INTERFACE)
            if props.Get(GATT_SERVICE_INTERFACE, "UUID") == self.SVC_UUID:
                logger.info('Service found: {}'.format(path))
                return service
        self._adapter.remove_device(self._device)
        raise SystemExit("Bluetooth Service not found!")

    def find_chrc(self, MSRMT_UUID):
        for path, ifaces in self._get_managed_objects().items():
            if GATT_CHRC_INTERFACE not in ifaces.keys():
                continue
            chrc = self._bus.get_object('org.bluez', path)
            props = dbus.Interface(chrc, PROP_INTERFACE)
            if props.Get(GATT_CHRC_INTERFACE, "UUID") == MSRMT_UUID:
                logger.info('Characteristic found: {}'.format(path))
                return chrc
        self._adapter.remove_device(self._device)
        raise SystemExit("Bluetooth Characteristic not found!")

    def _generic_error_cb(self, error):
        self._adapter.remove_device(self._device)
        self._main_loop.quit()
        raise SystemExit('D-Bus call failed: ' + str(error))

    def _start_notify_cb(self):
        logger.info('Notifications enabled')

    def _notify_timeout(self):
        self._adapter.remove_device(self._device)
        self._main_loop.quit()
        raise SystemExit('Notification test failed')

    def _changed_cb(self, iface, changed_props, invalidated_props):
        if iface != GATT_CHRC_INTERFACE:
            return
        if not len(changed_props):
            return
        value = changed_props.get('Value', None)
        if not value:
            return
        logger.debug('New Notification')
        self._notifications += 1
        if self._notifications >= self._max_notif:
            logger.info('Notification test succeeded')
            self._main_loop.quit()

    def check_notification(self, chrc, timeout=20):
        # Listen to PropertiesChanged signals from the BLE Measurement
        # Characteristic.
        prop_iface = dbus.Interface(chrc, PROP_INTERFACE)
        prop_iface.connect_to_signal("PropertiesChanged", self._changed_cb)

        # Subscribe to BLE Measurement notifications.
        chrc.StartNotify(reply_handler=self._start_notify_cb,
                         error_handler=self._generic_error_cb,
                         dbus_interface=GATT_CHRC_INTERFACE)
        GObject.timeout_add_seconds(timeout, self._notify_timeout)
        self._main_loop.run()


def main():
    logger.setLevel(logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "id",
        help='Address, udev path or name (hciX) of the BT adapter')
    parser.add_argument(
        "ADV_SVC_UUID", help='Beacon Gatt configuration service UUID')
    parser.add_argument(
        "SVC_UUID", help='Beacon Gatt notification service UUID')
    parser.add_argument("MSRMT_UUID", help='Beacon Gatt measurement UUID')
    parser.add_argument(
        "--max-notif", "-m", type=int, default=5,
        help="Maximum notification threshold")
    args = parser.parse_args()
    adapter = BtAdapter(args.id)
    adapter.ensure_powered()
    adapter.scan()
    device = adapter.find_device_with_service(args.ADV_SVC_UUID)
    try:
        device.Connect()
    except dbus.exceptions.DBusException as msg:
        logging.error(msg)
        adapter.remove_device(device)
        raise SystemExit(1)
    logger.info('Device connected, waiting 10s for services to be available')
    time.sleep(10)  # Let all the services to broadcast their UUIDs
    service = BtGATTRemoteService(
        args.SVC_UUID, adapter, device, args.max_notif)
    chrc = service.find_chrc(args.MSRMT_UUID)
    service.check_notification(chrc)
    try:
        device.Disconnect()
    except dbus.exceptions.DBusException as msg:
        logging.error(msg)
        adapter.remove_device(device)
        raise SystemExit(1)
    logger.info('Device properly disconnected')
    adapter.remove_device(device)


if __name__ == "__main__":
    sys.exit(main())
