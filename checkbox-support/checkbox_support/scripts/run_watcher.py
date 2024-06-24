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
import pathlib
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
    def _check_logs_for_insertion(self, line_str):
        """
        callback that looks for the expected log lines in the journal during
        the insertion test.
        """
        pass

    @abstractmethod
    def _check_logs_for_removal(self, line_str):
        """
        callback that looks for the expected log lines in the journal during
        the removal test.
        """
        pass

    @abstractmethod
    def _validate_insertion(self):
        pass

    @abstractmethod
    def _validate_removal(self):
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
            if self.testcase == "insertion":
                self._parse_journal_line(line_str)
                self._validate_insertion()
            elif self.testcase == "removal":
                self._parse_journal_line(line_str)
                self._validate_removal()

    def _store_storage_info(self, mounted_partition=""):
        """
        Store the mounted partition info to the shared directory.
        """

        plainbox_session_share = os.environ.get("PLAINBOX_SESSION_SHARE")
        # TODO: Should name the file by the value of storage_type variable as
        #       prefix. e.g. thunderbolt_insert_info, mediacard_insert_info.
        #       Since usb_insert_info is used by usb_read_write script, we
        #       should refactor usb_read_write script to adopt different files
        file_name = "usb_insert_info"

        if not plainbox_session_share:
            logger.error("no env var PLAINBOX_SESSION_SHARE")
            sys.exit(1)

        # backup the storage partition info
        if mounted_partition:
            logger.info(
                "cache file {} is at: {}".format(
                    file_name, plainbox_session_share
                )
            )
            file_path = pathlib.Path(plainbox_session_share, file_name)
            with open(file_path, "w") as file_to_share:
                file_to_share.write(mounted_partition + "\n")

    def _remove_storage_info(self):
        """Remove the file containing the storage info from the shared
        directory.
        """

        plainbox_session_share = os.environ.get("PLAINBOX_SESSION_SHARE")
        file_name = "usb_insert_info"

        if not plainbox_session_share:
            logger.error("no env var PLAINBOX_SESSION_SHARE")
            sys.exit(1)

        file_path = pathlib.Path(plainbox_session_share, file_name)
        if pathlib.Path(file_path).exists():
            os.remove(file_path)
            logger.info("cache file {} removed".format(file_name))
        else:
            logger.error("cache file {} not found".format(file_name))


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

    def _validate_insertion(self):
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

    def _validate_removal(self):
        if self.action == "removal":
            logger.info("Removal test passed.")

            # remove the storage info
            self._remove_storage_info()
            sys.exit()

    def _parse_journal_line(self, line_str):
        """
        Gets one of the lines from the journal and updates values of the
        device, driver, number and action attributes based on the line content.

        It uses dictionaries to match the expected log lines with the
        attributes.

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

        # Match the log line with the expected log lines and update the
        # corresponding attributes.
        for device_type, device_log in device_log_dict.items():
            if device_log in line_str:
                self.device = device_type

        for driver_type, driver_log in driver_log_dict.items():
            if driver_log in line_str:
                self.driver = driver_type
                self.number = re.search(
                    r"device number (\d+)", line_str
                ).group(1)

        # Look for insertion action
        if "USB Mass Storage device detected" in line_str:
            self.action = "insertion"

        # Look for removal action
        if "USB disconnect, device" in line_str:
            self.action = "removal"

        # Extract the partition name. Looking for string like "sdb: sdb1"
        part_re = re.compile("sd\w+:.*(?P<part_name>sd\w+)")
        match = re.search(part_re, line_str)
        if match:
            self.mounted_partition = match.group("part_name")


class MediacardStorage(StorageWatcher):
    """
    MediacardStorage handles the insertion and removal of sd, sdhc, mmc etc...
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.mounted_partition = None
        self.action = None
        self.device = None
        self.address = None

    def _validate_insertion(self):
        if self.mounted_partition and self.action == "insertion":
            logger.info("usable partition: {}".format(self.mounted_partition))
            logger.info(
                "{} card inserted. Address: {}".format(
                    self.device, self.address
                )
            )
            logger.info("Mediacard insertion test passed.")

            # backup the storage info
            self._store_storage_info(self.mounted_partition)
            sys.exit()

    def _validate_removal(self):
        if self.action == "removal":
            logger.info("Mediacard removal test passed.")

            # remove the storage info
            self._remove_storage_info()
            sys.exit()

    def _parse_journal_line(self, line_str):
        """
        Gets one of the lines from the journal and updates values of the
        mounted_partition attribute based on the line content.
        """

        # Extract the partition name. Looking for string like "mmcblk0: p1"
        part_re = re.compile("mmcblk(?P<dev_num>\d)+: (?P<part_name>p\d+)")
        match = re.search(part_re, line_str)
        if match:
            self.mounted_partition = "mmcblk{}{}".format(
                match.group("dev_num"), match.group("part_name")
            )

        # Look for insertion action
        insertion_re = re.compile(
            "new (?P<device>.*) card at address (?P<address>[0-9a-fA-F]+)"
        )
        insertion_match = re.search(insertion_re, line_str)
        if re.search(insertion_re, line_str):
            self.action = "insertion"
            self.device = insertion_match.group("device")
            self.address = insertion_match.group("address")

        # Look for removal action
        removal_re = re.compile("card ([0-9a-fA-F]+) removed")
        if re.search(removal_re, line_str):
            self.action = "removal"


class ThunderboltStorage(StorageWatcher):
    """
    ThunderboltStorage handles the insertion and removal of thunderbolt
    storage.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.mounted_partition = None
        self.action = None

    def _validate_insertion(self):
        # The insertion will be valid if the insertion action is detected and
        # the mounted partition is found.
        if self.action == "insertion" and self.mounted_partition:
            logger.info("usable partition: {}".format(self.mounted_partition))
            logger.info("Thunderbolt insertion test passed.")

            # backup the storage info
            self._store_storage_info(self.mounted_partition)
            sys.exit()

    def _validate_removal(self, line_str):
        if self.action == "removal":
            logger.info("Thunderbolt removal test passed.")

            # remove the storage info
            self._remove_storage_info()
            sys.exit()

    def _parse_journal_line(self, line_str):

        # Extract the partition name. Looking for string like "nvme0n1: p1"
        part_re = re.compile("(?P<dev_num>nvme\w+): (?P<part_name>p\d+)")
        match = re.search(part_re, line_str)
        if match:
            self.mounted_partition = "{}{}".format(
                match.group("dev_num"), match.group("part_name")
            )

        # Prefix of the thunderbolt device for regex matching
        RE_PREFIX = "thunderbolt \d+-\d+:"

        insertion_re = re.compile("{} new device found".format(RE_PREFIX))
        if re.search(insertion_re, line_str):
            self.action = "insertion"

        removal_re = re.compile("{} device disconnected".format(RE_PREFIX))
        if re.search(removal_re, line_str):
            self.action = "removal"


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
