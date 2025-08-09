#!/usr/bin/env python3

import sys
import dbus
import time
import logging

import checkbox_support.bt_helper as bt_helper
from checkbox_support.bt_helper import BtAdapter

PROP_INTERFACE = "org.freedesktop.DBus.Properties"


class Rfkill:
    """Settings Rfkill class."""

    RFKILL_INTERFACE = "org.gnome.SettingsDaemon.Rfkill"
    RFKILL_OBJ_PATH = "/org/gnome/SettingsDaemon/Rfkill"

    def __init__(self):
        self._bus = dbus.SessionBus()
        self._obj = self._bus.get_object(
            self.RFKILL_INTERFACE, self.RFKILL_OBJ_PATH
        )
        self._props = dbus.Interface(self._obj, PROP_INTERFACE)

    def set_prop(self, name, value):
        self._props.Set(self.RFKILL_INTERFACE, name, dbus.Boolean(value))

    def get_prop(self, name):
        return bool(self._props.Get(self.RFKILL_INTERFACE, name))


def check_bt_adapter_powered(adapter: BtAdapter, target: bool):
    timeout = 5
    delay = 1
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(delay)
        bt_adapter_state = adapter.get_bool_prop("Powered")
        if bt_adapter_state == target:
            return True

    return False


def test_bt_state():
    rfkill = Rfkill()
    bt_state = rfkill.get_prop("BluetoothAirplaneMode")
    rfkill.set_prop("BluetoothAirplaneMode", True)

    mgr = bt_helper.BtManager()
    for adapter in mgr.get_bt_adapters():
        ret = check_bt_adapter_powered(adapter, False)
        if not ret:
            logging.error(
                "{} Powered is not false".format(
                    adapter.get_string_prop("Address")
                )
            )
            return 1

    rfkill.set_prop("BluetoothAirplaneMode", False)
    for adapter in mgr.get_bt_adapters():
        ret = check_bt_adapter_powered(adapter, True)
        if not ret:
            logging.error(
                "{} Powered is not true".format(
                    adapter.get_string_prop("Address")
                )
            )
            return 1

    rfkill.set_prop("BluetoothAirplaneMode", bt_state)
    return 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(levelname)s: %(message)s",
    )

    return test_bt_state()


if __name__ == "__main__":
    sys.exit(main())
