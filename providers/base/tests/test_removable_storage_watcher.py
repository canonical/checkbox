import unittest
import sys
from unittest.mock import patch, MagicMock

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.exceptions"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

import removable_storage_watcher


class RemovableStorageWatcherTests(unittest.TestCase):

    @patch("removable_storage_watcher.connect_to_system_bus")
    @patch("removable_storage_watcher.is_udisks2_supported")
    @patch("removable_storage_watcher.UDisks1StorageDeviceListener")
    def test_main_udisk1(self, mock_udisk, mock_check, mock_connect):
        """
        Test the main function connects to the system bus,
        opens a UDisks1 listener and check the action is performed
        until timeout.
        """

        mock_connect.return_value = ("bus", "loop")
        mock_check.return_value = False

        argv = ["insert", "usb"]
        value = removable_storage_watcher.main(argv)

        mock_connect.assert_called_once_with()
        mock_udisk.assert_called_once_with(
            "bus",
            "loop",
            "insert",
            ["usb"],
            0,
            False,
        )

        mock_udisk.return_value.check.assert_called_once_with(20)

        self.assertEqual(value, mock_udisk.return_value.check.return_value)

    @patch("removable_storage_watcher.connect_to_system_bus")
    @patch("removable_storage_watcher.is_udisks2_supported")
    @patch("removable_storage_watcher.UDisks2StorageDeviceListener")
    def test_main_udisk2(self, mock_udisk, mock_check, mock_connect):
        """
        Test the main function uses a UDisks2 listener when
        supported.
        """

        mock_connect.return_value = ("bus", "loop")
        mock_check.return_value = True

        argv = ["insert", "usb"]
        removable_storage_watcher.main(argv)

        mock_udisk.assert_called_once_with(
            "bus",
            "loop",
            "insert",
            ["usb"],
            0,
            False,
            False,
        )

    @patch("removable_storage_watcher.connect_to_system_bus")
    @patch("removable_storage_watcher.is_udisks2_supported")
    @patch("removable_storage_watcher.UDisks1StorageDeviceListener")
    def test_main_interrupted(self, mock_udisk, mock_check, mock_connect):
        """
        Test the main function returns 1 when interrupted
        via CTRL-C
        """

        mock_connect.return_value = ("bus", "loop")
        mock_check.return_value = False

        argv = ["insert", "usb"]
        mock_udisk.return_value.check.side_effect = KeyboardInterrupt

        value = removable_storage_watcher.main(argv)
        self.assertEqual(value, 1)
