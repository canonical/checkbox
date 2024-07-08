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
from unittest.mock import patch, call, MagicMock, mock_open

import pathlib

from checkbox_support.scripts.run_watcher import (
    StorageWatcher,
    USBStorage,
    MediacardStorage,
    ThunderboltStorage,
    main,
)


class TestRunWatcher(unittest.TestCase):

    # class StorageWatcher(StorageInterface):
    #     """
    #     StorageWatcher watches the journal message and triggers the callback
    #     function to detect the insertion and removal of storage.
    #     """

    #     def __init__(self, testcase, storage_type, zapper_usb_address):
    #         self.testcase = testcase
    #         self.storage_type = storage_type
    #         self.zapper_usb_address = zapper_usb_address

    #     def run(self):
    #         j = journal.Reader()
    #         j.seek_realtime(time.time())
    #         p = select.poll()
    #         p.register(j, j.get_events())
    #         if self.zapper_usb_address:
    #             zapper_host = os.environ.get("ZAPPER_ADDRESS")
    #             if not zapper_host:
    #                 raise SystemExit(
    #                     "ZAPPER_ADDRESS environment variable not found!"
    #                 )
    #             usb_address = self.zapper_usb_address
    #             if self.testcase == "insertion":
    #                 print("Calling zapper to connect the USB device")
    #                 zapper_run(
    #                     zapper_host, "typecmux_set_state", usb_address, "DUT"
    #                 )
    #             elif self.testcase == "removal":
    #                 print("Calling zapper to disconnect the USB device")
    #                 zapper_run(
    #                     zapper_host, "typecmux_set_state", usb_address, "OFF"
    #                 )
    #         else:
    #             if self.testcase == "insertion":
    #                 print("\n\nINSERT NOW\n\n", flush=True)
    #             elif self.testcase == "removal":
    #                 print("\n\nREMOVE NOW\n\n", flush=True)
    #             else:
    #                 raise SystemExit("Invalid test case")
    #             print("Timeout: {} seconds".format(ACTION_TIMEOUT), flush=True)
    #         while p.poll():
    #             if j.process() != journal.APPEND:
    #                 continue
    #             self._process_lines(
    #                 [e["MESSAGE"] for e in j if e and "MESSAGE" in e]
    #             )

    #     def _process_lines(self, lines):
    #         """
    #         Process the lines from the journal and call the callback function to
    #         validate the insertion or removal of the storage.
    #         """
    #         for line in lines:
    #             line_str = str(line)
    #             logger.debug(line_str)
    #             if self.testcase == "insertion":
    #                 self._parse_journal_line(line_str)
    #                 self._validate_insertion()
    #             elif self.testcase == "removal":
    #                 self._parse_journal_line(line_str)
    #                 self._validate_removal()

    #     def _store_storage_info(self, mounted_partition=""):
    #         """
    #         Store the mounted partition info to the shared directory.
    #         """

    #         plainbox_session_share = os.environ.get("PLAINBOX_SESSION_SHARE")
    #         # TODO: Should name the file by the value of storage_type variable as
    #         #       prefix. e.g. thunderbolt_insert_info, mediacard_insert_info.
    #         #       Since usb_insert_info is used by usb_read_write script, we
    #         #       should refactor usb_read_write script to adopt different files
    #         file_name = "usb_insert_info"

    #         if not plainbox_session_share:
    #             logger.error("no env var PLAINBOX_SESSION_SHARE")
    #             sys.exit(1)

    #         # backup the storage partition info
    #         if mounted_partition:
    #             logger.info(
    #                 "cache file {} is at: {}".format(
    #                     file_name, plainbox_session_share
    #                 )
    #             )
    #             file_path = pathlib.Path(plainbox_session_share, file_name)
    #             with open(file_path, "w") as file_to_share:
    #                 file_to_share.write(mounted_partition + "\n")

    #     def _remove_storage_info(self):
    #         """Remove the file containing the storage info from the shared
    #         directory.
    #         """

    #         plainbox_session_share = os.environ.get("PLAINBOX_SESSION_SHARE")
    #         file_name = "usb_insert_info"

    #         if not plainbox_session_share:
    #             logger.error("no env var PLAINBOX_SESSION_SHARE")
    #             sys.exit(1)

    #         file_path = pathlib.Path(plainbox_session_share, file_name)
    #         if pathlib.Path(file_path).exists():
    #             os.remove(file_path)
    #             logger.info("cache file {} removed".format(file_name))
    #         else:
    #             logger.error("cache file {} not found".format(file_name))

    def test_storage_watcher_process_lines(self):
        lines = ["line1", "line2", "line3"]

        mock_insertion_watcher = MagicMock()
        mock_insertion_watcher._parse_journal_line = MagicMock()
        mock_insertion_watcher.testcase = "insertion"
        StorageWatcher._process_lines(mock_insertion_watcher, lines)
        mock_insertion_watcher._parse_journal_line.assert_has_calls(
            [call("line1"), call("line2"), call("line3")]
        )
        mock_insertion_watcher._validate_insertion.assert_called()

        mock_removal_watcher = MagicMock()
        mock_removal_watcher._parse_journal_line = MagicMock()
        mock_removal_watcher.testcase = "removal"
        StorageWatcher._process_lines(mock_removal_watcher, lines)
        mock_removal_watcher._parse_journal_line.assert_has_calls(
            [call("line1"), call("line2"), call("line3")]
        )
        mock_insertion_watcher._validate_insertion.assert_called()

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
        mock_usb_storage = MagicMock()

        line_str = "new high-speed USB device"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.device, "high_speed_usb")

        line_str = "new SuperSpeed USB device"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.device, "super_speed_usb")

        line_str = "new SuperSpeed Gen 1 USB device"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.device, "super_speed_gen1_usb")

        line_str = "new high-speed USB device number 1 using ehci_hcd"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.driver, "ehci_hcd")

        line_str = "new high-speed USB device number 4 using xhci_hcd"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.driver, "xhci_hcd")

        line_str = "USB Mass Storage device detected"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.action, "insertion")

        line_str = "USB disconnect, device"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.action, "removal")

        line_str = "sdb: sdb1"
        USBStorage._parse_journal_line(mock_usb_storage, line_str)
        self.assertEqual(mock_usb_storage.mounted_partition, "sdb1")

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
        mock_mediacard_storage = MagicMock()

        line_str = "mmcblk0: p1"
        MediacardStorage._parse_journal_line(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.mounted_partition, "mmcblk0p1")

        line_str = "new SD card at address 123456"
        MediacardStorage._parse_journal_line(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.action, "insertion")
        self.assertEqual(mock_mediacard_storage.device, "SD")
        self.assertEqual(mock_mediacard_storage.address, "123456")

        line_str = "card 123456 removed"
        MediacardStorage._parse_journal_line(mock_mediacard_storage, line_str)
        self.assertEqual(mock_mediacard_storage.action, "removal")

    # class ThunderboltStorage(StorageWatcher):
    #     """
    #     ThunderboltStorage handles the insertion and removal of thunderbolt
    #     storage.
    #     """

    #     def __init__(self, *args):
    #         super().__init__(*args)
    #         self.mounted_partition = None
    #         self.action = None

    #     def _validate_insertion(self):
    #         # The insertion will be valid if the insertion action is detected and
    #         # the mounted partition is found.
    #         if self.action == "insertion" and self.mounted_partition:
    #             logger.info("usable partition: {}".format(self.mounted_partition))
    #             logger.info("Thunderbolt insertion test passed.")

    #             # backup the storage info
    #             self._store_storage_info(self.mounted_partition)
    #             sys.exit()

    #     def _validate_removal(self, line_str):
    #         if self.action == "removal":
    #             logger.info("Thunderbolt removal test passed.")

    #             # remove the storage info
    #             self._remove_storage_info()
    #             sys.exit()

    #     def _parse_journal_line(self, line_str):

    #         # Extract the partition name. Looking for string like "nvme0n1: p1"
    #         part_re = re.compile("(?P<dev_num>nvme\w+): (?P<part_name>p\d+)")
    #         match = re.search(part_re, line_str)
    #         if match:
    #             self.mounted_partition = "{}{}".format(
    #                 match.group("dev_num"), match.group("part_name")
    #             )

    #         # Prefix of the thunderbolt device for regex matching
    #         RE_PREFIX = "thunderbolt \d+-\d+:"

    #         insertion_re = re.compile("{} new device found".format(RE_PREFIX))
    #         if re.search(insertion_re, line_str):
    #             self.action = "insertion"

    #         removal_re = re.compile("{} device disconnected".format(RE_PREFIX))
    #         if re.search(removal_re, line_str):
    #             self.action = "removal"

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
