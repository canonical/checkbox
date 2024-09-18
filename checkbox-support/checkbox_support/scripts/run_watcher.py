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
import logging
import os
import re
import select
import sys
import time
from systemd import journal
from abc import ABC, abstractmethod

from checkbox_support.helpers.timeout import timeout
from checkbox_support.scripts.zapper_proxy import zapper_run
from checkbox_support.scripts.usb_read_write import (
    mount_usb_storage,
    gen_random_file,
    write_test,
    read_test,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


ACTION_TIMEOUT = 30


class StorageInterface(ABC):
    """
    StorageInterface makes sure each type of storage class should implement
    these methods
    """

    @abstractmethod
    def _parse_journal_line(self, line_str):
        """
        Parse the journal line and update the attributes based on the line
        content.

        :param line_str: str of the scanned log lines.
        """
        pass

    @abstractmethod
    def _validate_insertion(self):
        """
        Check if the that the storage was inserted correctly.
        """
        pass

    @abstractmethod
    def _validate_removal(self):
        """
        Check if the that the storage was removed correctly.
        """
        pass


class StorageWatcher(StorageInterface):
    """
    StorageWatcher watches the journal message and triggers the callback
    function to detect the insertion and removal of storage.
    """

    def __init__(self, storage_type, zapper_usb_address):
        self.storage_type = storage_type
        self.zapper_usb_address = zapper_usb_address
        self.testcase = None
        self.test_passed = False
        self.mounted_partition = None

    def run(self):
        j = journal.Reader()
        j.seek_realtime(time.time())
        p = select.poll()
        p.register(j, j.get_events())
        if self.zapper_usb_address:
            zapper_host = os.environ.get("ZAPPER_HOST")
            if not zapper_host:
                raise SystemExit("ZAPPER_HOST environment variable not found!")
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
            if self.test_passed:
                return

    def _process_lines(self, lines):
        """
        Process the lines from the journal and call the callback function to
        validate the insertion or removal of the storage.
        """
        for line in lines:
            line_str = str(line)
            logger.debug(line_str)
            if self.testcase == "insertion":
                self._parse_journal_line(line_str)
                self._validate_insertion()
            elif self.testcase == "removal":
                self._parse_journal_line(line_str)
                self._validate_removal()
            if self.test_passed:
                return

    @timeout(ACTION_TIMEOUT)  # 30 seconds timeout
    def run_insertion(self):
        print("\n--------- Testing insertion ---------")
        self.testcase = "insertion"
        self.run()
        print("\n------- Insertion test passed -------")
        return self.mounted_partition

    @timeout(ACTION_TIMEOUT)  # 30 seconds timeout
    def run_removal(self, mounted_partition):
        print("\n---------- Testing removal ----------")
        self.testcase = "removal"
        self.mounted_partition = mounted_partition
        self.run()
        print("\n-------- Removal test passed --------")

    def run_storage(self, mounted_partition):
        print("\n--------- Testing read/write --------")
        with gen_random_file() as random_file:
            # initialize the necessary tasks before performing read/write test
            print("Mounting the USB storage")
            print(mounted_partition)
            with mount_usb_storage(mounted_partition):
                # write test
                write_test(random_file)
                # read test
                read_test(random_file)
        print("\n------- Read/Write test passed -------")


class USBStorage(StorageWatcher):
    """
    USBStorage handles the insertion and removal of usb2 and usb3.
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
                "super_speed_plus_gen2x1_usb",
            ]:
                logger.info("USB3 insertion test passed.")
            else:
                sys.exit("Wrong USB type detected.")

            self.test_passed = True

    def _validate_removal(self):
        if self.action == "removal":
            logger.info("Removal test passed.")
            self.test_passed = True

    def _parse_journal_line(self, line_str):
        """
        Gets one of the lines from the journal and updates values of the
        device, driver, number and action attributes based on the line content.

        It uses dictionaries to match the expected log lines with the
        attributes.
        """

        device_log_dict = {
            "high_speed_usb": "new high-speed USB device",
            "super_speed_usb": "new SuperSpeed USB device",
            "super_speed_gen1_usb": "new SuperSpeed Gen 1 USB device",
            "super_speed_plus_gen2x1_usb": "new SuperSpeed Plus Gen 2x1 USB device",
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
        if "USB Mass Storage device detected" in line_str or "uas" in line_str:
            self.action = "insertion"

        # Look for removal action
        if "USB disconnect, device" in line_str:
            self.action = "removal"

        # Extract the partition name. Looking for string like "sdb: sdb1"
        part_re = re.compile(r"sd\w+:.*(?P<part_name>sd\w+)")
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
            self.test_passed = True

    def _validate_removal(self):
        if self.action == "removal":
            logger.info("Mediacard removal test passed.")
            self.test_passed = True

    def _parse_journal_line(self, line_str):
        """
        Gets one of the lines from the journal and updates values of the
        mounted_partition attribute based on the line content.
        """

        # Extract the partition name. Looking for string like "mmcblk0: p1"
        part_re = re.compile(r"mmcblk(?P<dev_num>\d)+: (?P<part_name>p\d+)")
        match = re.search(part_re, line_str)
        if match:
            self.mounted_partition = "mmcblk{}{}".format(
                match.group("dev_num"), match.group("part_name")
            )

        # Look for insertion action
        insertion_re = re.compile(
            r"new (?P<device>.*) card at address (?P<address>[0-9a-fA-F]+)"
        )
        insertion_match = re.search(insertion_re, line_str)
        if re.search(insertion_re, line_str):
            self.action = "insertion"
            self.device = insertion_match.group("device")
            self.address = insertion_match.group("address")

        # Look for removal action
        removal_re = re.compile(r"card ([0-9a-fA-F]+) removed")
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
            self.test_passed = True

    def _validate_removal(self):
        if self.action == "removal":
            logger.info("Thunderbolt removal test passed.")
            self.test_passed = True

    def _parse_journal_line(self, line_str):

        # Extract the partition name. Looking for string like "nvme0n1: p1"
        part_re = re.compile(r"(?P<dev_num>nvme\w+): (?P<part_name>p\d+)")
        match = re.search(part_re, line_str)
        if match:
            self.mounted_partition = "{}{}".format(
                match.group("dev_num"), match.group("part_name")
            )

        # Prefix of the thunderbolt device for regex matching
        RE_PREFIX = r"thunderbolt \d+-\d+:"

        insertion_re = re.compile(r"{} new device found".format(RE_PREFIX))
        if re.search(insertion_re, line_str):
            self.action = "insertion"

        removal_re = re.compile(r"{} device disconnected".format(RE_PREFIX))
        if re.search(removal_re, line_str):
            self.action = "removal"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "testcase",
        choices=["insertion", "storage"],
        help=(
            "insertion: Tests insertion and removal of storage\n"
            "storage: Tests insertion, read and write, and removal\n"
        ),
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
    return parser.parse_args()


def main():
    args = parse_args()

    watcher = None
    if args.storage_type == "thunderbolt":
        watcher = ThunderboltStorage(
            args.storage_type, args.zapper_usb_address
        )
    elif args.storage_type == "mediacard":
        watcher = MediacardStorage(args.storage_type, args.zapper_usb_address)
    else:
        watcher = USBStorage(args.storage_type, args.zapper_usb_address)

    if args.testcase == "insertion":
        mounted_partition = watcher.run_insertion()
        watcher.run_removal(mounted_partition)
    elif args.testcase == "storage":
        mounted_partition = watcher.run_insertion()
        watcher.run_storage(mounted_partition)
        print("Press Enter to start removal", flush=True)
        input()
        watcher.run_removal(mounted_partition)
    else:
        raise SystemExit("Invalid test case")


if __name__ == "__main__":
    main()
