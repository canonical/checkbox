#!/usr/bin/env python3

import unittest
import sys
from unittest.mock import patch, MagicMock, Mock

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.service"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

from checkbox_support.helpers.retry import mock_retry

from bt_state_test import (
    check_bt_adapter_powered,
    bt_state_test,
    main,
    Rfkill,
)


class TestRfkill(unittest.TestCase):
    """This class provides test cases for the Rfkill helper."""

    def test_set_prop(self):
        rfkill = Rfkill()
        rfkill.set_prop("BluetoothAirplaneMode", True)
        rfkill._props.Set.assert_called_once()

    def test_get_prop(self):
        rfkill = Rfkill()
        rfkill._props.Get.return_value = True
        self.assertTrue(rfkill.get_prop("BluetoothAirplaneMode"))
        rfkill._props.Get.assert_called_once()


@mock_retry()
class TestBtStateTest(unittest.TestCase):
    """This class provides test cases for the BtStateTest."""

    def test_check_bt_adapter_powered_match(self):
        adapter = MagicMock()
        adapter.get_bool_prop.return_value = True
        check_bt_adapter_powered(adapter, True)
        adapter.get_bool_prop.return_value = False
        check_bt_adapter_powered(adapter, False)

    def test_check_bt_adapter_powered_mismatch(self):
        adapter = MagicMock()
        adapter.get_bool_prop.return_value = False
        with self.assertRaises(ValueError):
            check_bt_adapter_powered(adapter, True)

    @patch("bt_state_test.Rfkill")
    @patch("bt_state_test.bt_helper.BtManager")
    @patch("bt_state_test.check_bt_adapter_powered", Mock(return_value=None))
    def test_bt_state_success(self, mock_mgr, mock_rfkill):
        mock_rfkill.return_value.get_prop.return_value = False
        mock_mgr.return_value.get_bt_adapters.return_value = [MagicMock()]
        self.assertEqual(bt_state_test(), 0)

    @patch("bt_state_test.Rfkill")
    @patch("bt_state_test.bt_helper.BtManager")
    @patch("bt_state_test.check_bt_adapter_powered")
    def test_bt_state_power_off_fail(self, mock_check, mock_mgr, mock_rfkill):
        mock_check.side_effect = ValueError("Powered is True, expected False")
        mock_rfkill.return_value.get_prop.return_value = False
        mock_mgr.return_value.get_bt_adapters.return_value = [MagicMock()]
        self.assertEqual(bt_state_test(), 1)

    @patch("bt_state_test.Rfkill")
    @patch("bt_state_test.bt_helper.BtManager")
    @patch("bt_state_test.check_bt_adapter_powered")
    def test_bt_state_power_on_fail(self, mock_check, mock_mgr, mock_rfkill):
        mock_check.side_effect = [
            None,
            ValueError("Powered is False, expected True"),
        ]
        mock_rfkill.return_value.get_prop.return_value = False
        mock_mgr.return_value.get_bt_adapters.return_value = [MagicMock()]
        self.assertEqual(bt_state_test(), 1)

    @patch("bt_state_test.bt_state_test", Mock(return_value=0))
    def test_main(self):
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
