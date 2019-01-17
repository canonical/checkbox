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
import signal
import sys
from systemd import journal


logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))


class USBWatcher:

    PART_RE = re.compile("sd\w+:.*(?P<part_name>sd\w+)")
    USB_ACTION_TIMEOUT = 30  # sec
    FLAG_DETECTION = {"device": {
                      "new high-speed USB device number": False,
                      "new SuperSpeed USB device number": False
                      },
                      "driver": {
                          "using ehci_hcd": False,
                          "using xhci_hcd": False
                          },
                      "insertion": {
                          "USB Mass Storage device detected": False
                          },
                      "removal": {
                          "USB disconnect, device number": False,
                          "Aborting journal on device": False
                          }
                      }

    def __init__(self, args):
        self.args = args
        self.MOUNTED_PARTITION = None
        signal.signal(signal.SIGALRM, self._no_usb_timeout)
        signal.alarm(self.USB_ACTION_TIMEOUT)

    def run(self):
        j = journal.Reader()
        j.seek_tail()
        p = select.poll()
        p.register(j, j.get_events())
        if self.args.testcase == "insertion":
            print("\n\nINSERT NOW\n\n", flush=True)
        elif self.args.testcase == "removal":
            print("\n\nREMOVE NOW\n\n", flush=True)
        while p.poll():
            if j.process() != journal.APPEND:
                continue
            self._callback([e['MESSAGE'] for e in j if e and 'MESSAGE' in e])

    def _callback(self, lines):
        for line in lines:
            line_str = str(line)
            self._refresh_detection(line_str)
            self._get_partition_info(line_str)
            self._report_detection()

    def _get_partition_info(self, line_str):
        """get partition info."""
        # looking for string like "sdb: sdb1"
        match = re.search(self.PART_RE, line_str)
        if match:
            self.MOUNTED_PARTITION = match.group('part_name')

    def _refresh_detection(self, line_str):
        """
        refresh values of the dictionary FLAG_DETECTION.

        :param line_str: str of the scanned log lines.
        """
        for key in self.FLAG_DETECTION.keys():
            for sub_key in self.FLAG_DETECTION[key].keys():
                if sub_key in line_str:
                    self.FLAG_DETECTION[key][sub_key] = True

    def _report_detection(self):
        """report detection status."""
        # insertion detection
        if (
            self.args.testcase == "insertion" and
            self.FLAG_DETECTION["insertion"][
                "USB Mass Storage device detected"] and
            self.MOUNTED_PARTITION
        ):
            device = ""
            driver = ""
            for key in self.FLAG_DETECTION["device"]:
                if self.FLAG_DETECTION["device"][key]:
                    device = key
            for key in self.FLAG_DETECTION["driver"]:
                if self.FLAG_DETECTION["driver"][key]:
                    driver = key
            logger.info("%s was inserted %s controller" % (device, driver))
            logger.info("usable partition: %s" % self.MOUNTED_PARTITION)
            # judge the detection by the expection
            if (
                self.args.usb_type == 'usb2' and
                device == "new high-speed USB device number"
            ):
                logger.info("USB2 insertion test passed.")
                self._write_usb_info()
                sys.exit()
            if (
                self.args.usb_type == 'usb3' and
                device == "new SuperSpeed USB device number"
            ):
                logger.info("USB3 insertion test passed.")
                self._write_usb_info()
                sys.exit()
        elif (
            self.args.testcase == "insertion" and
            self.args.usb_type == "mediacard" and
            self.MOUNTED_PARTITION
        ):
            logger.info("usable partition: %s" % self.MOUNTED_PARTITION)
            logger.info("%s insertion test passed." % self.args.usb_type)
            self._write_usb_info()
            sys.exit()
        # removal detection
        if (
            self.args.testcase == "removal" and
            self.FLAG_DETECTION["removal"]["USB disconnect, device number"]
        ):
            logger.info("Removal test passed.")
            self._remove_usb_info()
            sys.exit()
        elif (
            self.args.testcase == "removal" and
            self.args.usb_type == "mediacard" and
            self.FLAG_DETECTION["removal"]["Aborting journal on device"]
        ):
            logger.info("Removal test passed.")
            self._remove_usb_info()
            sys.exit()

    def _write_usb_info(self):
        """
        reserve detected usb storage info.

        write the info we got in this script to $PLAINBOX_SESSION_SHARE
        so the other jobs, e.g. read/write test, could know more information,
        for example the partition it want to try to mount.
        """
        plainbox_session_share = os.environ.get('PLAINBOX_SESSION_SHARE')
        if not plainbox_session_share:
            logger.error("no env var PLAINBOX_SESSION_SHARE")
            sys.exit(1)
        if self.MOUNTED_PARTITION:
            logger.info(
                "cache file usb_insert_info is at: %s"
                % plainbox_session_share)
            file_to_share = open(
                os.path.join(plainbox_session_share, "usb_insert_info"), "w")
            file_to_share.write(self.MOUNTED_PARTITION + "\n")
            file_to_share.close()

    def _remove_usb_info(self):
        """remove usb storage info from $PLAINBOX_SESSION_SHARE."""
        plainbox_session_share = os.environ.get('PLAINBOX_SESSION_SHARE')
        if not plainbox_session_share:
            logger.error("no env var PLAINBOX_SESSION_SHARE")
            sys.exit(1)
            file_to_share = os.path.join(
                plainbox_session_share, "usb_insert_info")
            with contextlib.suppress(FileNotFoundError):
                os.remove(file_to_share)

    def _no_usb_timeout(self, signum, frame):
        """
        define timeout feature.

        timeout and return failure if there is no usb insertion/removal
        detected after USB_ACTION_TIMEOUT secs
        """
        logger.error(
            "no %s storage %s was reported in systemd journal",
            self.args.usb_type, self.args.testcase)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('testcase',
                        choices=['insertion', 'removal'],
                        help=("insertion or removal"))
    parser.add_argument('usb_type',
                        choices=['usb2', 'usb3', 'mediacard'],
                        help=("usb2 or usb3"))
    args = parser.parse_args()
    watcher = USBWatcher(args)
    watcher.run()


if __name__ == "__main__":
    main()
