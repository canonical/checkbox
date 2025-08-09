#!/usr/bin/env python3

import unittest
import sys
from unittest.mock import patch, MagicMock, Mock

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.service"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
from bt_state_test import (
    check_bt_adapter_powered,
    test_bt_state,
    main,
)


class TestBtStateTest(unittest.TestCase):
    """This class provides test cases for the BtStateTest."""

    def test_check_bt_adapter_powered(self):
        adapter = MagicMock()
        adapter.get_bool_prop.return_value = True
        self.assertEqual(check_bt_adapter_powered(adapter, True), True)
        adapter.get_bool_prop.return_value = False
        self.assertEqual(check_bt_adapter_powered(adapter, False), True)

    @patch("bt_state_test.Rfkill.set_prop", Mock(return_value=None))
    @patch("bt_state_test.check_bt_adapter_powered", Mock(return_value=True))
    def test_test_bt_state(self):
        a = MagicMock()
        rfkill = MagicMock()
        rfkill.get_prop.return_value = False
        mgr = MagicMock()
        mgr.get_bt_adapters.return_value = [a]
        self.assertEqual(test_bt_state(), 0)

    @patch("bt_state_test.test_bt_state", Mock(return_value=0))
    def test_main(self):
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
