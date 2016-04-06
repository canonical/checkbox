# Copyright 2016 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
"""
This module provides a set of abstractions to ease the process of automating
typical Bluetooth task like scanning for devices and pairing with them.

It talks with BlueZ stack using dbus.
"""
import logging

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GObject

logger = logging.getLogger(__file__)
logger.addHandler(logging.StreamHandler())

IFACE = 'org.bluez.Adapter1'
ADAPTER_IFACE = 'org.bluez.Adapter1'
DEVICE_IFACE = 'org.bluez.Device1'
AGENT_IFACE = 'org.bluez.Agent1'

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

# To get additional Bluetoot CoDs, check
# https://www.bluetooth.com/specifications/assigned-numbers/baseband
BT_ANY = 0
BT_KEYBOARD = int('0x2540', 16)


class BtException(Exception):
    pass


class BtManager:
    """ Main point of contact with dbus factoring bt objects. """
    def __init__(self, verbose=False):
        if verbose:
            logger.setLevel(logging.DEBUG)
        self._bus = dbus.SystemBus()
        self._bt_root = self._bus.get_object('org.bluez', '/')
        self._manager = dbus.Interface(
            self._bt_root, 'org.freedesktop.DBus.ObjectManager')
        self._main_loop = GObject.MainLoop()
        self._register_agent()

    def _register_agent(self):
        path = "/bt_helper/agent"
        BtAgent(self._bus, path)
        obj = self._bus.get_object('org.bluez', "/org/bluez")
        agent_manager = dbus.Interface(obj, "org.bluez.AgentManager1")
        agent_manager.RegisterAgent(path, 'NoInputNoOutput')
        logger.info("Agent registered")

    def _get_objects_by_iface(self, iface_name):
        for path, ifaces in self._manager.GetManagedObjects().items():
            if ifaces.get(iface_name):
                yield self._bus.get_object('org.bluez', path)

    def get_bt_adapters(self):
        """Yield BtAdapter objects for each BT adapter found."""
        for adapter in self._get_objects_by_iface(ADAPTER_IFACE):
            yield BtAdapter(dbus.Interface(adapter, ADAPTER_IFACE), self)

    def get_bt_devices(self, category=BT_ANY, filters={}):
        """Yields BtDevice objects currently known to the system.

        filters - specifies the characteristics of that a BT device must have
        to be yielded. The keys of filters dictionary represent names of
        parameters (as specified by the bluetooth DBus Api and represented by
        DBus proxy object), and its values must match proxy values.
        I.e. {'Paired': False}. For a full list of Parameters see:
        http://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc/device-api.txt

        Note that this function returns objects corresponding to BT devices
        that were seen last time scanning was done."""
        for device in self._get_objects_by_iface(DEVICE_IFACE):
            obj = self.get_object_by_path(device.object_path)[DEVICE_IFACE]
            try:
                if category != BT_ANY:
                    if obj['Class'] != category:
                        continue
                rejected = False
                for filter in filters:
                    if obj[filter] != filters[filter]:
                        rejected = True
                        break
                if rejected:
                    continue
                yield BtDevice(dbus.Interface(device, DEVICE_IFACE), self)
            except KeyError as exc:
                logger.info('Property %s not found on device %s',
                            exc, device.object_path)
                continue

    def get_prop_iface(self, obj):
        return dbus.Interface(self._bus.get_object(
            'org.bluez', obj.object_path), 'org.freedesktop.DBus.Properties')

    def get_object_by_path(self, path):
        return self._manager.GetManagedObjects()[path]

    def get_proxy_by_path(self, path):
        return self._bus.get_object('org.bluez', path)

    def wait(self):
        self._main_loop.run()

    def quit_loop(self):
        self._main_loop.quit()

    def ensure_adapters_powered(self):
        for adapter in self.get_bt_adapters():
            adapter.ensure_powered()

    def scan(self, timeout=10):
        """Scan for BT devices visible to all adapters.'"""
        self._bus.add_signal_receiver(
            interfaces_added,
            dbus_interface="org.freedesktop.DBus.ObjectManager",
            signal_name="InterfacesAdded")
        self._bus.add_signal_receiver(
            properties_changed,
            dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged",
            arg0="org.bluez.Device1",
            path_keyword="path")
        for adapter in self._get_objects_by_iface(ADAPTER_IFACE):
            try:
                dbus.Interface(adapter, ADAPTER_IFACE).StopDiscovery()
            except dbus.exceptions.DBusException:
                pass
            dbus.Interface(adapter, ADAPTER_IFACE).StartDiscovery()
        GObject.timeout_add_seconds(timeout, self._scan_timeout)
        self._main_loop.run()

    def get_devices(self, timeout=10, rescan=True):
        """Scan for and list all devices visible to all adapters."""
        if rescan:
            self.scan(timeout)
        return list(self.get_bt_devices())

    def _scan_timeout(self):
        for adapter in self._get_objects_by_iface(ADAPTER_IFACE):
            dbus.Interface(adapter, ADAPTER_IFACE).StopDiscovery()
        self._main_loop.quit()


class BtAdapter:
    def __init__(self, dbus_iface, bt_mgr):
        self._if = dbus_iface
        self._bt_mgr = bt_mgr
        self._prop_if = bt_mgr.get_prop_iface(dbus_iface)

    def set_bool_prop(self, prop_name, value):
        self._prop_if.Set(IFACE, prop_name, dbus.Boolean(value))

    def ensure_powered(self):
        """Turn the adapter on, and do nothing if already on."""
        powered = self._prop_if.Get(IFACE, 'Powered')
        logger.info('Powering on {}'.format(
            self._if.object_path.split('/')[-1]))
        if powered:
            logger.info('Device already powered')
            return
        try:
            self.set_bool_prop('Powered', True)
            logger.info('Powered on')
        except Exception as exc:
            logging.error('Failed to power on - {}'.format(
                exc.get_dbus_message()))


class BtDevice:
    def __init__(self, dbus_iface, bt_mgr):
        self._if = dbus_iface
        self._obj = bt_mgr.get_object_by_path(
            self._if.object_path)[DEVICE_IFACE]
        self._bt_mgr = bt_mgr
        self._prop_if = bt_mgr.get_prop_iface(dbus_iface)
        self._pair_outcome = None

    def __str__(self):
        return "{} ({})".format(self.name, self.address)

    def __repr__(self):
        return "<BtDevice name:{}, address:{}>".format(self.name, self.address)

    def pair(self):
        """Pair the device.

        This function will try pairing with the device and block until device
        is paired, error occured or default timeout elapsed (whichever comes
        first).
        """
        self._prop_if.Set(DEVICE_IFACE, 'Trusted', True)
        self._if.Pair(
            reply_handler=self._pair_ok, error_handler=self._pair_error)
        self._bt_mgr.wait()
        if self._pair_outcome:
            raise BtException(self._pair_outcome)
        try:
            self._if.Connect()
        except dbus.exceptions.DBusException as exc:
            logging.error('Failed to connect - {}'.format(
                exc.get_dbus_message()))

    def unpair(self):
        self._if.Disconnect()
        adapter = self._bt_mgr.get_proxy_by_path(self._obj['Adapter'])
        dbus.Interface(adapter, ADAPTER_IFACE).RemoveDevice(self._if)

    @property
    def name(self):
        return self._obj.get('Name', '<Unnamed>')

    @property
    def address(self):
        return self._obj['Address']

    @property
    def rssi(self):
        return self._obj.get('RSSI', None)

    def _pair_ok(self):
        logger.info('%s successfully paired', self.name)
        self._pair_outcome = None
        self._bt_mgr.quit_loop()

    def _pair_error(self, error):
        logger.warning('Pairing of %s device failed. %s', self.name, error)
        self._pair_outcome = error
        self._bt_mgr.quit_loop()


class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"


class BtAgent(dbus.service.Object):
    """Agent authenticating everything that is possible."""
    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        logger.info("AuthorizeService (%s, %s)", device, uuid)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        logger.info("RequestPasskey (%s)", device)
        passkey = input("Enter passkey: ")
        return dbus.UInt32(passkey)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        logger.info("RequestPinCode (%s)", device)
        return input("Enter PIN Code: ")

    @dbus.service.method(AGENT_IFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print("DisplayPasskey (%s, %06u entered %u)" %
              (device, passkey, entered), flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        logger.info("DisplayPinCode (%s, %s)", device, pincode)
        print('Type following pin on your device: {}'.format(pincode),
              flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        logger.info("RequestConfirmation (%s, %06d)", device, passkey)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        logger.info("RequestAuthorization (%s)", device)

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        logger.info("Cancelled")


def properties_changed(interface, changed, invalidated, path):
    logger.info('Property changed for device @ %s. Change: %s', path, changed)


def interfaces_added(path, interfaces):
    logger.info('Added new bt interfaces: %s @ %s', interfaces, path)
