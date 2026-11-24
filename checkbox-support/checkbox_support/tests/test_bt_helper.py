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
            {
                "/org/bluez/hci0": {bt_helper.ADAPTER_IFACE: {}},
                "/org/bluez/hci0/dev_00_11_22_33_44_56": {
                    bt_helper.DEVICE_IFACE: {"Paired": False}
                },
                path: {bt_helper.DEVICE_IFACE: props},
            },
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

    def test_trust_denied_is_not_reported_as_device_disappearance(self):
        manager = Mock()
        iface = Mock()
        manager.get_object_by_path.return_value = {
            self.bt_helper.DEVICE_IFACE: {"Address": "00:11:22:33:44:55"}
        }
        device = self.bt_helper.BtDevice(iface, manager)
        manager.get_object_by_path.assert_called_once_with(iface.object_path)
        error = FakeDBusException(
            name="org.freedesktop.DBus.Error.AccessDenied"
        )
        manager.get_prop_iface.return_value.Set.side_effect = error
        with self.assertRaises(FakeDBusException) as raised:
            device.pair()
        self.assertIs(raised.exception, error)
        iface.Pair.assert_not_called()

    def test_pairing_rejection_preserves_bluez_error(self):
        manager = Mock()
        iface = Mock()
        device = self.bt_helper.BtDevice(
            iface, manager, {"Address": "00:11:22:33:44:55"}
        )
        error = FakeDBusException(
            name="org.bluez.Error.AuthenticationRejected"
        )

        def reject_pairing():
            _, kwargs = iface.Pair.call_args
            kwargs["error_handler"](error)

        manager.wait.side_effect = reject_pairing
        with self.assertRaises(self.bt_helper.BtException) as raised:
            device.pair()
        self.assertEqual(raised.exception.args, (error,))
        iface.Connect.assert_not_called()

    def test_device_disappears_during_pair_request(self):
        for asynchronous in (False, True):
            with self.subTest(asynchronous=asynchronous):
                manager = Mock()
                iface = Mock()
                device = self.bt_helper.BtDevice(
                    iface, manager, {"Address": "00:11:22:33:44:55"}
                )
                error = FakeDBusException(
                    name="org.freedesktop.DBus.Error.UnknownObject"
                )
                if asynchronous:

                    def deliver_error():
                        _, kwargs = iface.Pair.call_args
                        kwargs["error_handler"](error)

                    manager.wait.side_effect = deliver_error
                else:
                    iface.Pair.side_effect = error

                with self.assertRaisesRegex(
                    self.bt_helper.BtException, "scan again"
                ) as raised:
                    device.pair()
                self.assertIs(raised.exception.__cause__, error)
                iface.Connect.assert_not_called()
