import sys
import unittest
from importlib.util import find_spec, module_from_spec
from unittest.mock import Mock, patch


class FakeDBusException(Exception):
    def __init__(self, *, name):
        super().__init__(name)
        self.name = name

    def get_dbus_name(self):
        return self.name


def load_bt_helper():
    dbus = Mock()
    dbus.DBusException = dbus.exceptions.DBusException = FakeDBusException
    dbus.service.Object = object
    dbus.service.method.return_value = lambda method: method
    gi = Mock()
    modules = {
        "dbus": dbus,
        "dbus.service": dbus.service,
        "dbus.mainloop": dbus.mainloop,
        "dbus.mainloop.glib": dbus.mainloop.glib,
        "gi": gi,
        "gi.repository": gi.repository,
    }
    spec = find_spec("checkbox_support.bt_helper")
    helper = module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(helper)
    return helper


class BtHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bt_helper = load_bt_helper()

    def test_device_list_uses_discovery_snapshot(self):
        bt_helper = self.bt_helper
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
        bt_helper = self.bt_helper
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
