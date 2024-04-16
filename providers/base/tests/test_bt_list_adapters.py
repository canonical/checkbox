import unittest
from unittest.mock import patch, mock_open
from pathlib import Path
from io import StringIO

import bt_list_adapters


class BTTests(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data=" test ")
    def test_get_node_content(self, mock_open):
        content = bt_list_adapters.get_node_content(Path("test"))
        self.assertEqual(content, "test")

    @patch("builtins.open", new_callable=mock_open, read_data="bluetooth")
    def test_is_bluetooth_adapter(self, mock_open):
        self.assertTrue(bt_list_adapters.is_bluetooth_adapter(Path("test")))

    @patch("builtins.open", new_callable=mock_open, read_data="not bluetooth")
    def test_is_not_bluetooth_adapter(self, mock_open):
        self.assertFalse(bt_list_adapters.is_bluetooth_adapter(Path("test")))

    def test_bt_adapter_not_found(self):
        list_bt_devices = bt_list_adapters.get_bluetooth_devices([])
        self.assertEqual(list_bt_devices, [])

    @patch("bt_list_adapters.is_bluetooth_adapter")
    @patch("bt_list_adapters.get_node_content")
    def test_bt_adapter_found(self, mock_content, mock_is_bt_adapter):
        mock_content.return_value = "test"
        mock_is_bt_adapter.return_value = True
        fake_devices = bt_list_adapters.get_bluetooth_devices([Path("/test")])
        self.assertEqual(fake_devices, [("test", "test")])

    @patch("bt_list_adapters.get_bluetooth_devices")
    @patch("bt_list_adapters.Path.iterdir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main(self, mock_stdout, mock_path, mock_bt_devices):
        mock_path.return_value = [
            "test",
        ]
        btdev = bt_list_adapters.BTDevice("test", "test")
        mock_bt_devices.return_value = [
            btdev,
        ]
        bt_list_adapters.main()
        self.assertEqual(mock_stdout.getvalue().strip(), "test test")

    @patch("bt_list_adapters.get_bluetooth_devices")
    @patch("bt_list_adapters.Path.iterdir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_no_bt_devices(self, mock_stdout, mock_path, mock_bt_devices):
        mock_path.return_value = []
        mock_bt_devices.return_value = []
        with self.assertRaises(SystemExit):
            bt_list_adapters.main()

    @patch("bt_list_adapters.get_bluetooth_devices")
    @patch("bt_list_adapters.Path.iterdir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_no_rfkill_path(
        self, mock_stdout, mock_path, mock_bt_devices
    ):
        mock_path.side_effect = FileNotFoundError
        mock_bt_devices.return_value = []
        with self.assertRaises(SystemExit):
            bt_list_adapters.main()
