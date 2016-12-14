#!/usr/bin/env python3
# Copyright 2015-2016 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Taihsiang Ho <taihsiang.ho@canonical.com>
"""
application to use LogWatcher.

this script use LogWatcher to define the actual behavior to watch log files by
a customized callback.
"""
import argparse
import contextlib
import sys
import os
import re
import signal
import logging
from checkbox_support.log_watcher import LogWatcher

global ARGS
USB_INSERT_TIMEOUT = 30  # sec

# {log_string_1:status_1, log_string_2:status_2 ...}
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
                      "USB disconnect, device number": False
                      }
                  }


MOUNTED_PARTITION_CANDIDATES = None
MOUNTED_PARTITION = None

logging.basicConfig(level=logging.WARNING)


######################################################
# run the log watcher
######################################################


def callback(filename, lines):
    """
    a callback function for LogWatcher.

    customized callback to define the actual behavior about how to watch and
    what to watch of the log files.

    :param filename: str, a text filename. usually be a log file.
    :param lines: list, contents the elements as string to tell what to watch.
    """
    for line in lines:
        line_str = str(line)
        refresh_detection(line_str)
        get_partition_info(line_str)
        report_detection()


def detect_str(line, str_2_detect):
    """detect the string in the line."""
    if str_2_detect in line:
        return True
    return False


def detect_partition(line):
    """
    detect device and partition info from lines.

    :param line:
        str, line string from log file

    :return :
        a list denoting [device, partition1, partition2 ...]
        from syslog
    """
    # looking for string like
    # sdb: sdb1
    pattern = "sd.+sd.+"
    match = re.search(pattern, line)
    if match:
        # remove the trailing \n and quote
        match_string = match.group()[:-3]
        # will looks like
        # ['sdb', ' sdb1']
        match_list = match_string.split(":")
        return match_list


def get_partition_info(line_str):
    """get partition info."""
    global MOUNTED_PARTITION_CANDIDATES, MOUNTED_PARTITION
    MOUNTED_PARTITION_CANDIDIATES = detect_partition(line_str)
    if (MOUNTED_PARTITION_CANDIDIATES and
       len(MOUNTED_PARTITION_CANDIDIATES) == 2):
        # hard code because I expect
        # FLAG_MOUNT_DEVICE_CANDIDIATES is something like ['sdb', ' sdb1']
        # This should be smarter if the device has multiple partitions.
        MOUNTED_PARTITION = MOUNTED_PARTITION_CANDIDIATES[1].strip()


def refresh_detection(line_str):
    """
    refresh values of the dictionary FLAG_DETECTION.

    :param line_str: str of the scanned log lines.
    """
    global FLAG_DETECTION
    for key in FLAG_DETECTION.keys():
        for sub_key in FLAG_DETECTION[key].keys():
            if detect_str(line_str, sub_key):
                FLAG_DETECTION[key][sub_key] = True


def report_detection():
    """report detection status."""
    # insertion detection
    if (
        ARGS.testcase == "insertion" and
        FLAG_DETECTION["insertion"]["USB Mass Storage device detected"] and
        MOUNTED_PARTITION
    ):
        device = ""
        driver = ""
        for key in FLAG_DETECTION["device"]:
            if FLAG_DETECTION["device"][key]:
                device = key
        for key in FLAG_DETECTION["driver"]:
            if FLAG_DETECTION["driver"][key]:
                driver = key
        logging.info("%s was inserted %s controller" % (device, driver))
        logging.info("usable partition: %s" % MOUNTED_PARTITION)

        # judge the detection by the expection
        if (
            ARGS.usb_type == 'usb2' and
            device == "new high-speed USB device number"
        ):
            print("USB2 insertion test passed.")
            write_usb_info()
            sys.exit()
        if (
            ARGS.usb_type == 'usb3' and
            device == "new SuperSpeed USB device number"
        ):
            print("USB3 insertion test passed.")
            write_usb_info()
            sys.exit()

    # removal detection
    if (
        ARGS.testcase == "removal" and
        FLAG_DETECTION["removal"]["USB disconnect, device number"]
    ):
        logging.info("An USB mass storage was removed.")
        remove_usb_info()
        sys.exit()


def write_usb_info():
    """
    reserve detected usb storage info.

    write the info we got in this script to $PLAINBOX_SESSION_SHARE
    so the other jobs, e.g. read/write test, could know more information,
    for example the partition it want to try to mount.
    """
    plainbox_session_share = os.environ.get('PLAINBOX_SESSION_SHARE')
    if not plainbox_session_share:
        logging.warning("no env var PLAINBOX_SESSION_SHARE")
        sys.exit(1)

    if MOUNTED_PARTITION:
        logging.info(
            "cache file usb_insert_info is at: %s" % plainbox_session_share)
        file_to_share = open(
            os.path.join(plainbox_session_share, "usb_insert_info"), "w")
        file_to_share.write(MOUNTED_PARTITION + "\n")
        file_to_share.close()


def remove_usb_info():
    """remove usb strage info from  $PLAINBOX_SESSION_SHARE."""
    plainbox_session_share = os.environ.get('PLAINBOX_SESSION_SHARE')
    if not plainbox_session_share:
        logging.warning("no env var PLAINBOX_SESSION_SHARE")
        sys.exit(1)
        file_to_share = os.path.join(plainbox_session_share, "usb_insert_info")
        with contextlib.suppress(FileNotFoundError):
            os.remove(file_to_share)


def no_usb_timeout(signum, frame):
    """
    define timeout feature.

    timeout and return failure if there is no usb insertion is detected
    after USB_INSERT_TIMEOUT secs
    """
    logging.info("no USB storage insertion was detected from /var/log/syslog")
    sys.exit(1)

def main():
    # access the parser
    parser = argparse.ArgumentParser()
    parser.add_argument('testcase',
                        choices=['insertion', 'removal'],
                        help=("insertion or removal"))
    parser.add_argument('usb_type',
                        choices=['usb2', 'usb3'],
                        help=("usb2 or usb3"))
    global ARGS
    ARGS = parser.parse_args()

    # set up the log watcher
    watcher = LogWatcher("/var/log", callback, logfile="syslog")
    signal.signal(signal.SIGALRM, no_usb_timeout)
    signal.alarm(USB_INSERT_TIMEOUT)
    watcher.loop()
