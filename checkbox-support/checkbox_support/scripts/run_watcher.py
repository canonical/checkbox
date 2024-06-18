#!/usr/bin/env python3
# Copyright 2015-2018 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Taihsiang Ho <taihsiang.ho@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
"""
this script monitors the systemd journal to catch insert/removal USB events
"""
import argparse
import contextlib
import logging
import os
import re
import select
import sys
import time
from systemd import journal
from abc import ABC, abstractmethod
from enum import Enum

from checkbox_support.helpers.timeout import timeout
from checkbox_support.scripts.zapper_proxy import zapper_run


logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

ACTION_TIMEOUT = 30


class StorageInterface(ABC):
    """
    StorageInterface makes sure each type of storage class should implement
    these methods
    """

    @abstractmethod
    def callback(self, line_str):
        """
        callback handles the line string from journal.
        """
        pass

    @abstractmethod
    def report_insertion(self):
        pass

    @abstractmethod
    def report_removal(self):
        pass


class StorageWatcher(StorageInterface):
    """
    StorageWatcher watches the journal message and triggers the callback
    function to detect the insertion and removal of storage.

    """

    def __init__(self, testcase, storage_type, zapper_usb_address):
        self.testcase = testcase
        self.storage_type = storage_type
        self.zapper_usb_address = zapper_usb_address

    def run(self):
        j = journal.Reader()
        j.seek_realtime(time.time())
        p = select.poll()
        p.register(j, j.get_events())
        if self.zapper_usb_address:
            zapper_host = os.environ.get("ZAPPER_ADDRESS")
            if not zapper_host:
                raise SystemExit(
                    "ZAPPER_ADDRESS environment variable not found!"
                )
            usb_address = self.zapper_usb_address
            if self.testcase == "insertion":
                print("Calling zapper to connect the USB device")
                zapper_run(
                    zapper_host, "typecmux_set_state", usb_address, "DUT"
                )
            elif self.testcase == "removal":
                print("Calling zapper to disconnect the USB device")
                zapper_run(
                    zapper_host, "typecmux_set_state", usb_address, "OFF"
                )
        else:
            if self.testcase == "insertion":
                print("\n\nINSERT NOW\n\n", flush=True)
            elif self.testcase == "removal":
                print("\n\nREMOVE NOW\n\n", flush=True)
            else:
                raise SystemExit("Invalid test case")
            print("Timeout: {} seconds".format(ACTION_TIMEOUT), flush=True)
        while p.poll():
            if j.process() != journal.APPEND:
                continue
            self._process_lines(
                [e["MESSAGE"] for e in j if e and "MESSAGE" in e]
            )

    def _process_lines(self, lines):
        for line in lines:
            line_str = str(line)
            logger.debug(line_str)
            self.callback(line_str)

    def _store_storage_info(self, mounted_partition=""):

        plainbox_session_share = os.environ.get("PLAINBOX_SESSION_SHARE")
        if not plainbox_session_share:
            logger.error("no env var PLAINBOX_SESSION_SHARE")
            sys.exit(1)

        # TODO: Should name the file by the value of storage_type variable as
        #       prefix. e.g. thunderbolt_insert_info, mediacard_insert_info.
        #       Since usb_insert_info is used by usb_read_write script, we
        #       should refactor usb_read_write script to adopt different files
        file_name = "usb_insert_info"

        # backup the storage partition info
        if mounted_partition:
            logger.info(
                "cache file {} is at: {}".format(
                    file_name, plainbox_session_share
                )
            )
            with open(
                os.path.join(plainbox_session_share, file_name), "w"
            ) as file_to_share:
                file_to_share.write(mounted_partition + "\n")

    def _remove_storage_info(self):

        plainbox_session_share = os.environ.get("PLAINBOX_SESSION_SHARE")
        file_name = "usb_insert_info"

        if not plainbox_session_share:
            logger.error("no env var PLAINBOX_SESSION_SHARE")
            sys.exit(1)
        file_to_share = os.path.join(plainbox_session_share, file_name)
        with contextlib.suppress(FileNotFoundError):
            os.remove(file_to_share)


class USBStorage(StorageWatcher):
    """
    USBStorage handles the insertion and removal of usb2, usb3 and mediacard.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.mounted_partition = None
        self.device = None
        self.number = None
        self.driver = None
        self.action = None

    def callback(self, line_str):
        self._refresh_detection(line_str)
        self._get_partition_info(line_str)
        self._report_detection()

    def report_insertion(self):
        if self.mounted_partition and self.action == "insertion":
            logger.info(
                "{} was inserted. Controller: {}, Number: {}".format(
                    self.device, self.driver, self.number
                )
            )
            logger.info("usable partition: {}".format(self.mounted_partition))
            # judge the detection by the expectation
            if self.storage_type == "usb2" and self.device == "high_speed_usb":
                logger.info("USB2 insertion test passed.")
            elif self.storage_type == "usb3" and self.device in [
                "super_speed_usb",
                "super_speed_gen1_usb",
            ]:
                logger.info("USB3 insertion test passed.")
            else:
                sys.exit("Wrong USB type detected.")

            # backup the storage info
            self._store_storage_info(self.mounted_partition)
            sys.exit()

    def report_removal(self):
        if self.action == "removal":
            logger.info("Removal test passed.")

            # remove the storage info
            self._remove_storage_info()
            sys.exit()

    def _get_partition_info(self, line_str):
        """get partition info."""
        # looking for string like "sdb: sdb1"
        part_re = re.compile("sd\w+:.*(?P<part_name>sd\w+)")
        match = re.search(part_re, line_str)
        if match:
            self.mounted_partition = match.group("part_name")

    def _refresh_detection(self, line_str):
        """
        refresh values with the lines from journal.

        :param line_str: str of the scanned log lines.
        """

        device_log_dict = {
            "high_speed_usb": "new high-speed USB device",
            "super_speed_usb": "new SuperSpeed USB device",
            "super_speed_gen1_usb": "new SuperSpeed Gen 1 USB device",
        }

        driver_log_dict = {
            "ehci_hcd": "using ehci_hcd",
            "xhci_hcd": "using xhci_hcd",
        }

        action_log_dict = {
            "insertion": "USB Mass Storage device detected",
            "removal": "USB disconnect, device",
        }

        for device_type, device_log in device_log_dict.items():
            if device_log in line_str:
                self.device = device_type

        for driver_type, driver_log in driver_log_dict.items():
            if driver_log in line_str:
                self.driver = driver_type
                self.number = re.search(
                    r"device number (\d+)", line_str
                ).group(1)

        for action_type, action_log in action_log_dict.items():
            if action_log in line_str:
                self.action = action_type

    def _report_detection(self):
        """report detection status."""
        if self.testcase == "insertion":
            self.report_insertion()
        elif self.testcase == "removal":
            self.report_removal()


class MediacardStorage(StorageWatcher):
    """
    MediacardStorage handles the insertion and removal of sd, sdhc, mmc etc...
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.mounted_partition = None

    def callback(self, line_str):
        if self.testcase == "insertion":
            self._get_partition_info(line_str)
            self.report_insertion()
        elif self.testcase == "removal":
            self.report_removal(line_str)

    def report_insertion(self):
        if self.mounted_partition:
            logger.info("usable partition: {}".format(self.mounted_partition))
            logger.info("Mediacard insertion test passed.")
            sys.exit()

    def report_removal(self, line_str):
        MMC_RE = re.compile("card [0-9a-fA-F]+ removed")
        # since the mmc addr in kernel message is not static, so use
        # regex to judge it
        match = re.search(MMC_RE, line_str)

        if match:
            logger.info("Mediacard removal test passed.")

            # Storage removal info
            self._remove_storage_info()
            sys.exit()

    def _get_partition_info(self, line_str):
        """get partition info."""

        # Match something like "mmcblk0: p1".
        part_re = re.compile("mmcblk(?P<dev_num>\d)+: (?P<part_name>p\d+)")
        match = re.search(part_re, line_str)
        if match:
            self.mounted_partition = "mmcblk{}{}".format(
                match.group("dev_num"), match.group("part_name")
            )
            # backup the storage info
            self._store_storage_info(self.mounted_partition)


class ThunderboltStorage(StorageWatcher):
    """
    ThunderboltStorage handles the insertion and removal of thunderbolt
    storage.
    """

    RE_PREFIX = "thunderbolt \d+-\d+:"

    def __init__(self, *args):
        super().__init__(*args)
        self.find_insertion_string = 0
        self.find_partition = 0

    def callback(self, line_str):
        if self.testcase == "insertion":
            self._get_partition_info(line_str)
            self.report_insertion(line_str)
            # The new device string be shown quite early than partition name
            # in journal. Thererfore, the insertion will be considered as
            # success until the requirement of new device string and partition
            # marked as true
            if self.find_insertion_string and self.find_partition:
                logger.info("Thunderbolt insertion test passed.")
                sys.exit()
        elif self.testcase == "removal":
            self.report_removal(line_str)

    def report_insertion(self, line_str):
        """
        Find the expected string while thunderbolt storage be inserted.
        """
        insert_re = re.compile("{} new device found".format(self.RE_PREFIX))
        match = re.search(insert_re, line_str)
        if match:
            self.find_insertion_string = 1
            logger.debug("find new thunderbolt device string in journal")

    def report_removal(self, line_str):
        """
        Find the expected string while thunderbolt storage be removed.
        """
        remove_re = re.compile("{} device disconnected".format(self.RE_PREFIX))
        match = re.search(remove_re, line_str)
        if match:
            logger.info("Thunderbolt removal test passed.")
            # Storage removal info
            self._remove_storage_info()
            sys.exit()

    def _get_partition_info(self, line_str):
        """get partition info."""
        # looking for string like "nvme0n1: p1"
        part_re = re.compile("(?P<dev_num>nvme\w+): (?P<part_name>p\d+)")
        match = re.search(part_re, line_str)
        if match:
            self.find_partition = 1
            # backup the storage info
            self.mounted_partition = "{}{}".format(
                match.group("dev_num"), match.group("part_name")
            )
            self._store_storage_info(self.mounted_partition)

@timeout(ACTION_TIMEOUT)  # 30 seconds timeout
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "testcase",
        choices=["insertion", "removal"],
        help=("insertion or removal"),
    )
    parser.add_argument(
        "storage_type",
        choices=["usb2", "usb3", "mediacard", "thunderbolt"],
        help=("usb2, usb3, mediacard or thunderbolt"),
    )
    parser.add_argument(
        "--zapper-usb-address",
        type=str,
        help="Zapper's USB switch address to use",
    )
    args = parser.parse_args()

    watcher = None
    if args.storage_type == "thunderbolt":
        watcher = ThunderboltStorage(
            args.testcase, args.storage_type, args.zapper_usb_address
        )
    elif args.storage_type == "mediacard":
        watcher = MediacardStorage(
            args.testcase, args.storage_type, args.zapper_usb_address
        )
    else:
        watcher = USBStorage(
            args.testcase, args.storage_type, args.zapper_usb_address
        )
    watcher.run()


if __name__ == "__main__":
    main()
