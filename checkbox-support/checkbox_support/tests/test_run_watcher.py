#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Authors:
#   Fernando Bravo <daniel.manrique@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import unittest
from unittest.mock import patch, call, MagicMock

from checkbox_support.scripts.run_watcher import (
    StorageWatcher,
    USBStorage,
    MediacardStorage,
    ThunderboltStorage,
    main,
)


class TestRunWatcher(unittest.TestCase):

    def test_process_lines(self):
        mock_storage_watcher = MagicMock()
        mock_storage_watcher.callback = MagicMock()
        lines = ["line1", "line2", "line3"]
        StorageWatcher._process_lines(mock_storage_watcher, lines)
        mock_storage_watcher.callback.assert_has_calls(
            [call("line1"), call("line2"), call("line3")]
        )

    def test_usb_storage_init(self):
        usb_storage = USBStorage("args")
        self.assertEqual(usb_storage.args, "args")
        self.assertIsNone(usb_storage.mounted_partition)
        self.assertIsNone(usb_storage.device)
        self.assertIsNone(usb_storage.number)
        self.assertIsNone(usb_storage.driver)
        self.assertIsNone(usb_storage.action)

    def test_usb_storage_callback(self):
        mock_usb_storage = MagicMock()
        line_str = "line_str"
        USBStorage.callback(mock_usb_storage, line_str)
        mock_usb_storage._refresh_detection.assert_called_with(line_str)
        mock_usb_storage._get_partition_info.assert_called_with(line_str)
        mock_usb_storage._report_detection.assert_called_with()

    def test_usb2_storage_report_insertion(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.args.storage_type = "usb2"
        mock_usb_storage.device = USBStorage.Device.HIGH_SPEED_USB
        mock_usb_storage.mounted_partition = "mounted_partition"
        mock_usb_storage.action = USBStorage.Action.INSERTION
        mock_usb_storage.driver = USBStorage.Driver.USING_EHCI_HCD
        with self.assertRaises(SystemExit) as cm:
            USBStorage.report_insertion(mock_usb_storage)
        self.assertEqual(cm.exception.code, None)

    def test_usb3_storage_report_insertion(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.args.storage_type = "usb3"
        mock_usb_storage.device = USBStorage.Device.SUPER_SPEED_USB
        mock_usb_storage.mounted_partition = "mounted_partition"
        mock_usb_storage.action = USBStorage.Action.INSERTION
        mock_usb_storage.driver = USBStorage.Driver.USING_XHCI_HCD
        with self.assertRaises(SystemExit) as cm:
            USBStorage.report_insertion(mock_usb_storage)
        self.assertEqual(cm.exception.code, None)

    def test_usb_storage_report_insertion_wrong_usb_type(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.args.storage_type = "usb2"
        mock_usb_storage.device = USBStorage.Device.SUPER_SPEED_USB
        mock_usb_storage.mounted_partition = "mounted_partition"
        mock_usb_storage.action = USBStorage.Action.INSERTION
        mock_usb_storage.driver = USBStorage.Driver.USING_XHCI_HCD
        with self.assertRaises(SystemExit) as cm:
            USBStorage.report_insertion(mock_usb_storage)
        cm.exception.args[0] == "Wrong USB type detected."

    def test_usb_storage_report_removal(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.action = USBStorage.Action.REMOVAL
        with self.assertRaises(SystemExit) as cm:
            USBStorage.report_removal(mock_usb_storage)
        self.assertEqual(cm.exception.code, None)

    def test_usb_storage_get_partition_info(self):
        mock_usb_storage = MagicMock()
        line_str = "sdb: sdb1"
        USBStorage._get_partition_info(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.mounted_partition, "sdb1")

    def test_usb_storage_refresh_detection(self):
        mock_usb_storage = MagicMock()
        line_str = "new high-speed USB device number 2 using xhci_hcd"
        USBStorage._refresh_detection(mock_usb_storage, line_str)
        self.assertEqual(
            mock_usb_storage.driver, USBStorage.Driver.USING_XHCI_HCD
        )
        self.assertEqual(
            mock_usb_storage.device, USBStorage.Device.HIGH_SPEED_USB
        )
        line_str = "USB Mass Storage device detected"
        USBStorage._refresh_detection(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.action, USBStorage.Action.INSERTION)

    def test_usb_storage_report_detection_insertion(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.args.testcase = "insertion"
        USBStorage._report_detection(mock_usb_storage)
        mock_usb_storage.report_insertion.assert_any_call()

    def test_usb_storage_report_detection_removal(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.args.testcase = "removal"
        USBStorage._report_detection(mock_usb_storage)
        mock_usb_storage.report_removal.assert_any_call()

    def test_mediacard_storage_callback_insertion(self):
        mock_mediacard_storage = MagicMock()
        line_str = "line_str"
        mock_mediacard_storage.args.testcase = "insertion"
        MediacardStorage.callback(mock_mediacard_storage, line_str)
        mock_mediacard_storage._get_partition_info.assert_called_with(line_str)
        mock_mediacard_storage.report_insertion.assert_any_call()

    def test_mediacard_storage_callback_removal(self):
        mock_mediacard_storage = MagicMock()
        line_str = "line_str"
        mock_mediacard_storage.args.testcase = "removal"
        MediacardStorage.callback(mock_mediacard_storage, line_str)
        mock_mediacard_storage.report_removal.assert_called_with(line_str)

    def test_mediacard_storage_report_insertion(self):
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.mounted_partition = "mounted_partition"
        with self.assertRaises(SystemExit):
            MediacardStorage.report_insertion(mock_mediacard_storage)

    def test_mediacard_storage_no_insertion(self):
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.mounted_partition = None
        MediacardStorage.report_insertion(mock_mediacard_storage)

    def test_mediacard_storage_report_removal(self):
        mock_mediacard_storage = MagicMock()
        line_str = "card 12 removed"
        with self.assertRaises(SystemExit) as cm:
            MediacardStorage.report_removal(mock_mediacard_storage, line_str)
        self.assertEqual(cm.exception.code, None)

    def test_mediacard_storage_no_removal(self):
        mock_mediacard_storage = MagicMock()
        line_str = ""
        MediacardStorage.report_removal(mock_mediacard_storage, line_str)

    def test_mediacard_storage_get_partition_info(self):
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.args.storage_type = "mediacard"
        line_str = "mmcblk0: p1"
        MediacardStorage._get_partition_info(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.mounted_partition, "mmcblk0p1")
        mock_mediacard_storage._storage_info_helper.assert_called_with(
            reserve=True,
            storage_type="mediacard",
            mounted_partition="mmcblk0p1",
        )

    def test_thunderbolt_storage_init(self):
        thunderbolt_storage = ThunderboltStorage("args")
        self.assertEqual(thunderbolt_storage.args, "args")
        self.assertEqual(thunderbolt_storage.find_insertion_string, 0)
        self.assertEqual(thunderbolt_storage.find_partition, 0)

    def test_thunderbolt_storage_report_insertion(self):
        mock_thunderbolt_storage = MagicMock()
        mock_thunderbolt_storage.RE_PREFIX = "thunderbolt \d+-\d+:"
        mock_thunderbolt_storage.args.testcase = "insertion"
        line_str = "thunderbolt 1-1: new device found"
        ThunderboltStorage.report_insertion(mock_thunderbolt_storage, line_str)
        self.assertEqual(mock_thunderbolt_storage.find_insertion_string, 1)

    def test_thunderbolt_storage_report_removal(self):
        mock_thunderbolt_storage = MagicMock()
        mock_thunderbolt_storage.RE_PREFIX = "thunderbolt \d+-\d+:"
        mock_thunderbolt_storage.args.testcase = "removal"
        line_str = "thunderbolt 1-1: device disconnected"
        with self.assertRaises(SystemExit) as cm:
            ThunderboltStorage.report_removal(
                mock_thunderbolt_storage, line_str
            )
        self.assertEqual(cm.exception.code, None)

    @patch("checkbox_support.scripts.run_watcher.USBStorage", spec=USBStorage)
    def test_main_usb(self, mock_usb_storage):
        with patch("sys.argv", ["run_watcher.py", "insertion", "usb2"]):
            main()
        # get the watcher object from main
        watcher = mock_usb_storage.return_value
        # check that the watcher is an USBStorage object
        self.assertIsInstance(watcher, USBStorage)

    @patch(
        "checkbox_support.scripts.run_watcher.MediacardStorage",
        spec=MediacardStorage,
    )
    def test_main_mediacard(self, mock_mediacard_storage):
        with patch("sys.argv", ["run_watcher.py", "insertion", "mediacard"]):
            main()
        # get the watcher object from main
        watcher = mock_mediacard_storage.return_value
        # check that the watcher is an MediacardStorage object
        self.assertIsInstance(watcher, MediacardStorage)

    @patch(
        "checkbox_support.scripts.run_watcher.ThunderboltStorage",
        spec=ThunderboltStorage,
    )
    def test_main_thunderbolt(self, mock_thunderbolt_storage):
        with patch("sys.argv", ["run_watcher.py", "insertion", "thunderbolt"]):
            main()
        # get the watcher object from main
        watcher = mock_thunderbolt_storage.return_value
        # check that the watcher is an ThunderboltStorage object
        self.assertIsInstance(watcher, ThunderboltStorage)
