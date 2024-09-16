#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Authors:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
from unittest.mock import patch, call, MagicMock, mock_open

import pathlib
from systemd import journal

from checkbox_support.scripts.run_watcher import (
    StorageWatcher,
    USBStorage,
    MediacardStorage,
    ThunderboltStorage,
    launch_watcher,
)


class TestRunWatcher(unittest.TestCase):

    @patch("systemd.journal.Reader")
    @patch("select.poll")
    def test_storage_watcher_run_insertion(self, mock_poll, mock_journal):
        mock_journal.return_value.process.side_effect = [journal.APPEND, None]
        mock_journal.return_value.__iter__.return_value = [
            {"MESSAGE": "line1"}
        ]
        mock_poll.return_value.poll.side_effect = [True, True, False]

        mock_storage_watcher = MagicMock()
        mock_storage_watcher.zapper_usb_address = ""

        # Test insertion
        mock_storage_watcher.testcase = "insertion"
        StorageWatcher.run(mock_storage_watcher)
        mock_storage_watcher._process_lines.assert_called_with(["line1"])

    @patch("systemd.journal.Reader")
    @patch("select.poll")
    def test_storage_watcher_run_removal(self, mock_poll, mock_journal):
        mock_journal.return_value.process.return_value = journal.APPEND
        mock_journal.return_value.__iter__.return_value = [
            {"MESSAGE": "line1"}
        ]
        mock_poll.return_value.poll.side_effect = [True, False]

        mock_storage_watcher = MagicMock()
        mock_storage_watcher.zapper_usb_address = ""

        # Test removal
        mock_storage_watcher.testcase = "removal"
        StorageWatcher.run(mock_storage_watcher)
        mock_storage_watcher._process_lines.assert_called_with(["line1"])

    def test_storage_watcher_run_invalid_testcase(self):
        mock_storage_watcher = MagicMock()
        mock_storage_watcher.testcase = "invalid"

        with self.assertRaises(SystemExit):
            StorageWatcher.run(mock_storage_watcher)

    @patch("systemd.journal.Reader")
    @patch("select.poll")
    @patch("os.environ.get")
    @patch("checkbox_support.scripts.run_watcher.zapper_run")
    def test_storage_watcher_run_insertion_with_zapper(
        self, mock_zapper_run, mock_get, mock_poll, mock_journal
    ):
        mock_journal.return_value.process.return_value = journal.APPEND
        mock_journal.return_value.__iter__.return_value = [
            {"MESSAGE": "line1"}
        ]
        mock_poll.return_value.poll.side_effect = [True, False]
        mock_get.return_value = "zapper_addr"

        mock_storage_watcher = MagicMock()
        mock_storage_watcher.zapper_usb_address = "usb_address"

        # Test insertion with zapper
        mock_storage_watcher.testcase = "insertion"
        StorageWatcher.run(mock_storage_watcher)
        mock_zapper_run.assert_called_with(
            "zapper_addr", "typecmux_set_state", "usb_address", "DUT"
        )
        mock_storage_watcher._process_lines.assert_called_with(["line1"])

    @patch("systemd.journal.Reader")
    @patch("select.poll")
    @patch("os.environ.get")
    @patch("checkbox_support.scripts.run_watcher.zapper_run")
    def test_storage_watcher_run_removal_with_zapper(
        self, mock_zapper_run, mock_get, mock_poll, mock_journal
    ):
        mock_journal.return_value.process.return_value = journal.APPEND
        mock_journal.return_value.__iter__.return_value = [
            {"MESSAGE": "line1"}
        ]
        mock_poll.return_value.poll.side_effect = [True, False]
        mock_get.return_value = "zapper_addr"

        mock_storage_watcher = MagicMock()
        mock_storage_watcher.zapper_usb_address = "usb_address"

        # Test removal with zapper
        mock_storage_watcher.testcase = "removal"
        StorageWatcher.run(mock_storage_watcher)
        mock_zapper_run.assert_called_with(
            "zapper_addr", "typecmux_set_state", "usb_address", "OFF"
        )
        mock_storage_watcher._process_lines.assert_called_with(["line1"])

    def test_storage_watcher_process_lines_insertion(self):
        lines = ["line1", "line2", "line3"]

        mock_insertion_watcher = MagicMock()
        mock_insertion_watcher._parse_journal_line = MagicMock()
        mock_insertion_watcher.testcase = "insertion"
        StorageWatcher._process_lines(mock_insertion_watcher, lines)
        mock_insertion_watcher._parse_journal_line.assert_has_calls(
            [call("line1"), call("line2"), call("line3")]
        )

    def test_storage_watcher_process_lines_removal(self):
        lines = ["line1", "line2", "line3"]

        mock_removal_watcher = MagicMock()
        mock_removal_watcher._parse_journal_line = MagicMock()
        mock_removal_watcher.testcase = "removal"
        StorageWatcher._process_lines(mock_removal_watcher, lines)
        mock_removal_watcher._parse_journal_line.assert_has_calls(
            [call("line1"), call("line2"), call("line3")]
        )

    @patch("os.environ.get")
    def test_storage_watcher_store_storage_info(self, mock_get):
        mock_storage_watcher = MagicMock()
        mock_get.return_value = "/tmp"

        mock_storage_watcher.storage_type = "usb2"
        mounted_partition = "sda1"

        m = mock_open()
        with patch("builtins.open", m):
            StorageWatcher._store_storage_info(
                mock_storage_watcher, mounted_partition
            )

        m.assert_called_with(pathlib.Path("/tmp", "usb_insert_info"), "w")
        m().write.assert_called_with("sda1\n")

    @patch("os.environ.get")
    def test_storage_watcher_store_storage_info_no_session(self, mock_get):
        mock_storage_watcher = MagicMock()
        mock_get.return_value = None

        with self.assertRaises(SystemExit):
            StorageWatcher._store_storage_info(mock_storage_watcher)

    @patch("pathlib.Path.exists")
    @patch("os.remove")
    @patch("os.environ.get")
    def test_storage_watcher_remove_storage_info(
        self, mock_get, mock_remove, mock_exists
    ):
        mock_storage_watcher = MagicMock()
        mock_get.return_value = "/tmp"
        mock_exists.return_value = True

        StorageWatcher._remove_storage_info(mock_storage_watcher)

        mock_remove.assert_called_with(pathlib.Path("/tmp", "usb_insert_info"))

    @patch("pathlib.Path.exists")
    @patch("os.remove")
    @patch("os.environ.get")
    def test_storage_watcher_remove_storage_info_no_file(
        self, mock_get, mock_remove, mock_exists
    ):
        mock_storage_watcher = MagicMock()
        mock_get.return_value = "/tmp"
        mock_exists.return_value = False

        StorageWatcher._remove_storage_info(mock_storage_watcher)

        mock_remove.assert_not_called()

    @patch("os.environ.get")
    def test_storage_watcher_remove_storage_info_no_session(self, mock_get):
        mock_storage_watcher = MagicMock()
        mock_get.return_value = None

        with self.assertRaises(SystemExit):
            StorageWatcher._remove_storage_info(mock_storage_watcher)

    def test_usb_storage_init(self):
        usb_storage = USBStorage("insertion", "usb2", "zapper_addr")
        self.assertEqual(usb_storage.testcase, "insertion")
        self.assertEqual(usb_storage.storage_type, "usb2")
        self.assertEqual(usb_storage.zapper_usb_address, "zapper_addr")
        self.assertIsNone(usb_storage.mounted_partition)
        self.assertIsNone(usb_storage.device)
        self.assertIsNone(usb_storage.number)
        self.assertIsNone(usb_storage.driver)
        self.assertIsNone(usb_storage.action)

    def test_usb2_storage_validate_insertion(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.storage_type = "usb2"
        mock_usb_storage.device = "high_speed_usb"
        mock_usb_storage.mounted_partition = "mounted_partition"
        mock_usb_storage.action = "insertion"
        mock_usb_storage.driver = "ehci_hcd"
        with self.assertRaises(SystemExit) as cm:
            USBStorage._validate_insertion(mock_usb_storage)
        self.assertEqual(cm.exception.code, None)

    def test_usb3_storage_validate_insertion(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.storage_type = "usb3"
        mock_usb_storage.device = "super_speed_usb"
        mock_usb_storage.mounted_partition = "mounted_partition"
        mock_usb_storage.action = "insertion"
        mock_usb_storage.driver = "xhci_hcd"
        with self.assertRaises(SystemExit) as cm:
            USBStorage._validate_insertion(mock_usb_storage)
        self.assertEqual(cm.exception.code, None)

    def test_usb3_gen2x1_storage_validate_insertion(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.storage_type = "usb3"
        mock_usb_storage.device = "super_speed_plus_gen2x1_usb"
        mock_usb_storage.mounted_partition = "mounted_partition"
        mock_usb_storage.action = "insertion"
        mock_usb_storage.driver = "xhci_hcd"
        with self.assertRaises(SystemExit) as cm:
            USBStorage._validate_insertion(mock_usb_storage)
        self.assertEqual(cm.exception.code, None)

    def test_usb_storage_validate_insertion_wrong_usb_type(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.storage_type = "usb2"
        mock_usb_storage.device = "super_speed_usb"
        mock_usb_storage.mounted_partition = "mounted_partition"
        mock_usb_storage.action = "insertion"
        mock_usb_storage.driver = "ehci_hcd"
        with self.assertRaises(SystemExit) as cm:
            USBStorage._validate_insertion(mock_usb_storage)
        cm.exception.args[0] == "Wrong USB type detected."

    def test_usb_storage_validate_removal(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.action = "removal"
        with self.assertRaises(SystemExit) as cm:
            USBStorage._validate_removal(mock_usb_storage)
        self.assertEqual(cm.exception.code, None)

    def test_usb_storage_no_insertion(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.mounted_partition = None
        mock_usb_storage.action = ""
        USBStorage._validate_insertion(mock_usb_storage)

    def test_usb_storage_no_removal(self):
        mock_usb_storage = MagicMock()
        mock_usb_storage.action = ""
        USBStorage._validate_removal(mock_usb_storage)

    def test_usb_storage_parse_journal_line(self):
        line_str = "new high-speed USB device"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.device, "high_speed_usb")

        line_str = "new SuperSpeed USB device"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.device, "super_speed_usb")

        line_str = "new SuperSpeed Gen 1 USB device"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.device, "super_speed_gen1_usb")

        line_str = "new SuperSpeed Plus Gen 2x1 USB device"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(
            mock_usb_storage.device, "super_speed_plus_gen2x1_usb"
        )

        line_str = "new high-speed USB device number 1 using ehci_hcd"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.driver, "ehci_hcd")

        line_str = "new high-speed USB device number 4 using xhci_hcd"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.driver, "xhci_hcd")

        line_str = "USB Mass Storage device detected"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.action, "insertion")

        line_str = "kernel: scsi host0: uas"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.action, "insertion")

        line_str = "USB disconnect, device"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.action, "removal")

        line_str = "sdb: sdb1"
        mock_usb_storage = MagicMock()
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.mounted_partition, "sdb1")

        line_str = "Invalid line"
        mock_usb_storage = MagicMock()
        mock_usb_storage.action = None
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.action, None)

    def test_mediacard_storage_init(self):
        mediacard_storage = MediacardStorage(
            "insertion", "mediacard", "zapper_addr"
        )
        self.assertEqual(mediacard_storage.testcase, "insertion")
        self.assertEqual(mediacard_storage.storage_type, "mediacard")
        self.assertEqual(mediacard_storage.zapper_usb_address, "zapper_addr")
        self.assertIsNone(mediacard_storage.mounted_partition)

    def test_mediacard_storage_validate_insertion(self):
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.mounted_partition = "mmcblk0p1"
        mock_mediacard_storage.action = "insertion"
        mock_mediacard_storage.device = "SD"
        mock_mediacard_storage.address = "123456"
        with self.assertRaises(SystemExit) as cm:
            MediacardStorage._validate_insertion(mock_mediacard_storage)
        self.assertEqual(cm.exception.code, None)

    def test_mediacard_storage_validate_removal(self):
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.action = "removal"
        with self.assertRaises(SystemExit) as cm:
            MediacardStorage._validate_removal(mock_mediacard_storage)
        self.assertEqual(cm.exception.code, None)

    def test_mediacard_storage_no_insertion(self):
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.mounted_partition = None
        mock_mediacard_storage.action = ""
        MediacardStorage._validate_insertion(mock_mediacard_storage)

    def test_mediacard_storage_no_removal(self):
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.action = ""
        MediacardStorage._validate_removal(mock_mediacard_storage)

    def test_mediacard_storage_parse_journal_line(self):
        line_str = "mmcblk0: p1"
        mock_mediacard_storage = MagicMock()
        MediacardStorage._parse_journal_line(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.mounted_partition, "mmcblk0p1")

        line_str = "new SD card at address 123456"
        mock_mediacard_storage = MagicMock()
        MediacardStorage._parse_journal_line(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.action, "insertion")
        self.assertEqual(mock_mediacard_storage.device, "SD")
        self.assertEqual(mock_mediacard_storage.address, "123456")

        line_str = "card 123456 removed"
        mock_mediacard_storage = MagicMock()
        MediacardStorage._parse_journal_line(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.action, "removal")

        line_str = "Invalid line"
        mock_mediacard_storage = MagicMock()
        mock_mediacard_storage.action = None
        MediacardStorage._parse_journal_line(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.action, None)

    def test_thunderbolt_storage_init(self):
        thunderbolt_storage = ThunderboltStorage(
            "insertion", "thunderbolt", "zapper_addr"
        )
        self.assertEqual(thunderbolt_storage.testcase, "insertion")
        self.assertEqual(thunderbolt_storage.storage_type, "thunderbolt")
        self.assertEqual(thunderbolt_storage.zapper_usb_address, "zapper_addr")
        self.assertIsNone(thunderbolt_storage.mounted_partition)
        self.assertIsNone(thunderbolt_storage.action)

    def test_thunderbolt_storage_validate_insertion(self):
        mock_thunderbolt_storage = MagicMock()
        mock_thunderbolt_storage.mounted_partition = "nvme0n1p1"
        mock_thunderbolt_storage.action = "insertion"
        with self.assertRaises(SystemExit) as cm:
            ThunderboltStorage._validate_insertion(mock_thunderbolt_storage)
        self.assertEqual(cm.exception.code, None)

    def test_thunderbolt_storage_validate_removal(self):
        mock_thunderbolt_storage = MagicMock()
        mock_thunderbolt_storage.action = "removal"
        with self.assertRaises(SystemExit) as cm:
            ThunderboltStorage._validate_removal(mock_thunderbolt_storage)
        self.assertEqual(cm.exception.code, None)

    def test_thunderbolt_storage_no_insertion(self):
        mock_thunderbolt_storage = MagicMock()
        mock_thunderbolt_storage.mounted_partition = None
        mock_thunderbolt_storage.action = ""
        ThunderboltStorage._validate_insertion(mock_thunderbolt_storage)

    def test_thunderbolt_storage_no_removal(self):
        mock_thunderbolt_storage = MagicMock()
        mock_thunderbolt_storage.action = ""
        ThunderboltStorage._validate_removal(mock_thunderbolt_storage)

    def test_thunderbolt_storage_parse_journal_line(self):
        line_str = "nvme0n1: p1"
        mock_thunderbolt_storage = MagicMock()
        ThunderboltStorage._parse_journal_line(
            mock_thunderbolt_storage, line_str
        )
        self.assertEqual(
            mock_thunderbolt_storage.mounted_partition, "nvme0n1p1"
        )

        line_str = "thunderbolt 1-1: new device found"
        mock_thunderbolt_storage = MagicMock()
        ThunderboltStorage._parse_journal_line(
            mock_thunderbolt_storage, line_str
        )
        self.assertEqual(mock_thunderbolt_storage.action, "insertion")

        line_str = "thunderbolt 1-1: device disconnected"
        mock_thunderbolt_storage = MagicMock()
        ThunderboltStorage._parse_journal_line(
            mock_thunderbolt_storage, line_str
        )
        self.assertEqual(mock_thunderbolt_storage.action, "removal")

        line_str = "Invalid line"
        mock_thunderbolt_storage = MagicMock()
        mock_thunderbolt_storage.action = None
        MediacardStorage._parse_journal_line(
            mock_thunderbolt_storage, line_str
        )
        self.assertEqual(mock_thunderbolt_storage.action, None)

    @patch("checkbox_support.scripts.run_watcher.USBStorage", spec=USBStorage)
    def test_main_usb(self, mock_usb_storage):
        with patch("sys.argv", ["run_watcher.py", "insertion", "usb2"]):
            launch_watcher()
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
            launch_watcher()
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
            launch_watcher()
        # get the watcher object from main
        watcher = mock_thunderbolt_storage.return_value
        # check that the watcher is an ThunderboltStorage object
        self.assertIsInstance(watcher, ThunderboltStorage)
