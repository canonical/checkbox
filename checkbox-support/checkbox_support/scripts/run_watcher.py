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

    def __init__(self, args):
        self.args = args

    def run(self):
        j = journal.Reader()
        j.seek_realtime(time.time())
        p = select.poll()
        p.register(j, j.get_events())
        if self.args.zapper_usb_address:
            zapper_host = os.environ.get("ZAPPER_ADDRESS")
            if not zapper_host:
                raise SystemExit(
                    "ZAPPER_ADDRESS environment variable not found!"
                )
            usb_address = self.args.zapper_usb_address
            if self.args.testcase == "insertion":
                print("Calling zapper to connect the USB device")
                zapper_run(
                    zapper_host, "typecmux_set_state", usb_address, "DUT"
                )
            elif self.args.testcase == "removal":
                print("Calling zapper to disconnect the USB device")
                zapper_run(
                    zapper_host, "typecmux_set_state", usb_address, "OFF"
                )
        else:
            if self.args.testcase == "insertion":
                print("\n\nINSERT NOW\n\n", flush=True)
            elif self.args.testcase == "removal":
                print("\n\nREMOVE NOW\n\n", flush=True)
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

    def _storage_info_helper(self, reserve, mounted_partition=""):
        """
        Reserve or removal the detected storage info.

        write the info we got in this script to $PLAINBOX_SESSION_SHARE
        so the other jobs, e.g. read/write test, could know more information,
        for example the partition it want to try to mount.

        :param reserve:
            type: Boolean
            - True: backup the info of storage partition to PLAINBOX_SESSION_SHARE
            - False: remove the backup file from PLAINBOX_SESSION_SHARE
        :param storage_type:
            type: String
            - Type of storage. e.g. usb, mediacard and thunderbolt
        :param mounted_partition:
            type: String
            - The name of partition. e.g. sda1, nvme1n1p1 etc...
        """
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
        if reserve and mounted_partition:
            logger.info(
                "cache file {} is at: {}".format(
                    file_name, plainbox_session_share
                )
            )
            file_to_share = open(
                os.path.join(plainbox_session_share, file_name), "w"
            )
            file_to_share.write(mounted_partition + "\n")
            file_to_share.close()

        # remove the back info
        if not reserve:
            file_to_share = os.path.join(plainbox_session_share, file_name)
            with contextlib.suppress(FileNotFoundError):
                os.remove(file_to_share)


class USBStorage(StorageWatcher):
    """
    USBStorage handles the insertion and removal of usb2, usb3 and mediacard.
    """

    class Device(Enum):
        HIGH_SPEED_USB = "new high-speed USB device"
        SUPER_SPEED_USB = "new SuperSpeed USB device"
        SUPER_SPEED_GEN1_USB = "new SuperSpeed Gen 1 USB device"

    class Driver(Enum):
        USING_EHCI_HCD = "using ehci_hcd"
        USING_XHCI_HCD = "using xhci_hcd"

    class Action(Enum):
        INSERTION = "USB Mass Storage device detected"
        REMOVAL = "USB disconnect, device"

    def __init__(self, args):
        self.args = args
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
        if (
            self.mounted_partition
            and self.action == USBStorage.Action.INSERTION
        ):
            logger.info(
                "{} was inserted {} controller".format(
                    self.device.value, self.driver.value
                )
            )
            logger.info("usable partition: {}".format(self.mounted_partition))
            # judge the detection by the expectation
            if (
                self.args.storage_type == "usb2"
                and self.device == USBStorage.Device.HIGH_SPEED_USB
            ):
                logger.info("USB2 insertion test passed.")
            elif self.args.storage_type == "usb3" and self.device in [
                USBStorage.Device.SUPER_SPEED_USB,
                USBStorage.Device.SUPER_SPEED_GEN1_USB,
            ]:
                logger.info("USB3 insertion test passed.")
            else:
                sys.exit("Wrong USB type detected.")

            # backup the storage info
            self._storage_info_helper(
                reserve=True,
                storage_type=self.args.storage_type,
                mounted_partition=self.mounted_partition,
            )
            sys.exit()

    def report_removal(self):
        if self.action == USBStorage.Action.REMOVAL:
            logger.info("Removal test passed.")

            # remove the storage info
            self._storage_info_helper(
                reserve=False, storage_type=self.args.storage_type
            )
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
        for driver in USBStorage.Driver:
            if driver.value in line_str:
                self.driver = driver
        for device in USBStorage.Device:
            if device.value in line_str:
                self.device = device
                # Get the device number after "device number "
                self.number = re.search(
                    r"device number (\d+)", line_str
                ).group(1)
        for action in USBStorage.Action:
            if action.value in line_str:
                self.action = action

    def _report_detection(self):
        """report detection status."""
        if self.args.testcase == "insertion":
            self.report_insertion()
        elif self.args.testcase == "removal":
            self.report_removal()


class MediacardStorage(StorageWatcher):
    """
    MediacardStorage handles the insertion and removal of sd, sdhc, mmc etc...
    """

    mounted_partition = None

    def callback(self, line_str):
        if self.args.testcase == "insertion":
            self._get_partition_info(line_str)
            self.report_insertion()
        elif self.args.testcase == "removal":
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
            self._storage_info_helper(
                reserve=False, storage_type=self.args.storage_type
            )
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
            self._storage_info_helper(
                reserve=True,
                storage_type=self.args.storage_type,
                mounted_partition=self.mounted_partition,
            )


class ThunderboltStorage(StorageWatcher):
    """
    ThunderboltStorage handles the insertion and removal of thunderbolt
    storage.
    """

    RE_PREFIX = "thunderbolt \d+-\d+:"

    def __init__(self, args):
        self.args = args
        self.find_insertion_string = 0
        self.find_partition = 0

    def callback(self, line_str):
        if self.args.testcase == "insertion":
            self._get_partition_info(line_str)
            self.report_insertion(line_str)
            # The new device string be shown quite early than partition name
            # in journal. Thererfore, the insertion will be considered as
            # success until the requirement of new device string and partition
            # marked as true
            if self.find_insertion_string and self.find_partition:
                logger.info("Thunderbolt insertion test passed.")
                sys.exit()
        elif self.args.testcase == "removal":
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
            self._storage_info_helper(
                reserve=False, storage_type=self.args.storage_type
            )
            sys.exit()

    def _get_partition_info(self, line_str):
        """get partition info."""
        # looking for string like "nvme0n1: p1"
        part_re = re.compile("(?P<dev_num>nvme\w+): (?P<part_name>p\d+)")
        match = re.search(part_re, line_str)
        if match:
            self.find_partition = 1
            # backup the storage info
            self._storage_info_helper(
                reserve=True,
                storage_type=self.args.storage_type,
                mounted_partition="{}{}".format(
                    match.group("dev_num"), match.group("part_name")
                ),
            )


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
        watcher = ThunderboltStorage(args)
    elif args.storage_type == "mediacard":
        watcher = MediacardStorage(args)
    else:
        watcher = USBStorage(args)
    watcher.run()


if __name__ == "__main__":
    main()
