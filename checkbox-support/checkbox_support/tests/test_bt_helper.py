import unittest
from unittest.mock import Mock, patch

try:
    from checkbox_support import bt_helper
except ModuleNotFoundError as exc:
    if exc.name not in ("dbus", "gi"):
        raise
    raise unittest.SkipTest(
        "Bluetooth tests require dbus-python and PyGObject"
    )


class BtHelperTests(unittest.TestCase):
    def test_device_list_uses_discovery_snapshot(self):
        manager = bt_helper.BtManager.__new__(bt_helper.BtManager)
        manager._manager = Mock()
        manager._bus = Mock()
        path = "/org/bluez/hci0/dev_00_11_22_33_44_55"
        props = {"Address": "00:11:22:33:44:55", "Icon": "input-mouse"}
        manager._manager.GetManagedObjects.side_effect = [
            {path: {bt_helper.DEVICE_IFACE: props}},
            {},
        ]
        with patch.object(bt_helper.dbus, "Interface"):
            devices = list(
                manager.get_bt_devices(filters={"Icon": "input-mouse"})
            )
        self.assertEqual(
            [device.address for device in devices], [props["Address"]]
        )
        manager._manager.GetManagedObjects.assert_called_once_with()

    def test_selected_device_disappears_before_pairing(self):
        manager = Mock()
        iface = Mock()
        device = bt_helper.BtDevice(
            iface, manager, {"Address": "00:11:22:33:44:55"}
        )
        manager.get_prop_iface.return_value.Set.side_effect = (
            bt_helper.dbus.exceptions.DBusException(
                name="org.freedesktop.DBus.Error.UnknownObject"
            )
        )
        with self.assertRaisesRegex(bt_helper.BtException, "scan again"):
            device.pair()
        iface.Pair.assert_not_called()
