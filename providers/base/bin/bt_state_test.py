#!/usr/bin/env python3

import sys
import dbus
import logging

import checkbox_support.bt_helper as bt_helper
from checkbox_support.bt_helper import BtAdapter
from checkbox_support.helpers.retry import retry

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
        """Set a boolean property on the Settings Rfkill interface."""
        self._props.Set(self.RFKILL_INTERFACE, name, dbus.Boolean(value))

    def get_prop(self, name):
        """Return a boolean property from the Settings Rfkill interface."""
        return bool(self._props.Get(self.RFKILL_INTERFACE, name))


@retry(max_attempts=5, delay=1)
def check_bt_adapter_powered(adapter: BtAdapter, target: bool):
    """Check that a Bluetooth adapter's Powered state matches target.

    The adapter needs some time to follow the airplane-mode setting, so the
    check is retried for a few seconds. Raise ValueError if the state never
    matches ``target``.
    """
    bt_adapter_state = adapter.get_bool_prop("Powered")
    if bt_adapter_state != target:
        address = adapter.get_string_prop("Address")
        raise ValueError(
            f"{address} Powered is {bt_adapter_state}, expected {target}"
        )


def bt_state_test():
    """Check that the adapter state follows the airplane-mode setting.

    Toggle the Settings ``BluetoothAirplaneMode`` on and off and verify that
    every Bluetooth adapter's ``Powered`` state follows accordingly, then
    restore the original setting. Return 0 on success, 1 on mismatch.
    """
    rfkill = Rfkill()
    bt_state = rfkill.get_prop("BluetoothAirplaneMode")

    logging.info("Enabling Bluetooth airplane mode from Settings...")
    rfkill.set_prop("BluetoothAirplaneMode", True)

    mgr = bt_helper.BtManager()
    for adapter in mgr.get_bt_adapters():
        address = adapter.get_string_prop("Address")
        logging.info(
            f"Checking adapter {address} is powered off in airplane mode..."
        )
        try:
            check_bt_adapter_powered(adapter, False)
        except ValueError as exc:
            logging.error(exc)
            return 1
        logging.info(f"Adapter {address} is correctly powered off")

    logging.info("Disabling Bluetooth airplane mode from Settings...")
    rfkill.set_prop("BluetoothAirplaneMode", False)
    for adapter in mgr.get_bt_adapters():
        address = adapter.get_string_prop("Address")
        logging.info(
            f"Checking adapter {address} is powered on out of airplane "
            "mode..."
        )
        try:
            check_bt_adapter_powered(adapter, True)
        except ValueError as exc:
            logging.error(exc)
            return 1
        logging.info(f"Adapter {address} is correctly powered on")

    logging.info("Restoring original Bluetooth airplane mode setting...")
    rfkill.set_prop("BluetoothAirplaneMode", bt_state)
    logging.info("Bluetooth adapter state matches the Settings UI")
    return 0


def main():
    """Set up logging and run the Bluetooth state alignment test."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(levelname)s: %(message)s",
    )

    return bt_state_test()


if __name__ == "__main__":
    sys.exit(main())
