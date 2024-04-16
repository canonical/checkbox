#!/usr/bin/env python3
"""
Script to automate disk SMART testing.

Copyright (C) 2010-2016 Canonical Ltd.

Authors
  Jeff Lane <jeffrey.lane@canonical.com>
  Brendan Donegan <brendan.donegan@canonical.com>
  Rod Smith <rod.smith@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

The purpose of this script is to simply interact with an onboard hard disk and
check for SMART capability and then do a little bit of interaction to make sure
we can at least do some limited interaction with the hard disk's SMART
functions.

We assume that SMART is available. The test will fail if this is not the case.
The block_device_resource script includes a test of SMART availability.
Checkbox tests for SMART availability as part of the disk/smart provider
definition, which uses block_device_resource as part of its requires: test.

This script runs the SMART short self test. It returns 0 if it's all good,
and 1 if it fails.

NOTE: This may not work correctly on systems where the onboard storage is
controlled by a hardware RAID controller, on external RAID systems, SAN, and
USB/eSATA/eSAS attached storage devices. Such systems should be filtered
out by the SMART availability test in block_device_resource.

Changelog:

v1.4: Fix script failure on disks with no pre-existing SMART tests
v1.3: Fix detection of SMART availability & activate SMART if available
      but deactivated. Also use smartctl return value rather than string-
      matching to determine if a test has failed; this should be more
      robust, as output strings vary between disks.
v1.2: Handle multiple output formats for "smartctl -l"
v1.1: Put delay before first attempt to acces log, rather than after
v1.0: added debugger class and code to allow for verbose debug output if needed

v0.4: corrected some minor things
      added option parsing to allow for many disks, or disks other than
      "/dev/sda"

V0.3: Removed the arbitrary wait time and implemented a polling method
    to shorten the test time.
    Added in Pass/Fail criteria for the final outcome.
    Added in documentation.

V0.2: added minor debug routine

V0.1: Fixed some minor bugs and added the SmartEnabled() function

V0: First draft

"""

import os
import sys
import time
import logging
import shlex

from subprocess import Popen, PIPE, check_call, check_output
from subprocess import CalledProcessError
from argparse import ArgumentParser

# NOTE: If raid_types changes, also change it in block_device_resource script!
raid_types = ["megaraid", "cciss", "3ware", "areca"]


class ListHandler(logging.StreamHandler):

    def emit(self, record):
        if isinstance(record.msg, (list, tuple)):
            for msg in record.msg:
                if type(msg) is bytes:
                    msg = msg.decode()
                logger = logging.getLogger(record.name)
                new_record = logger.makeRecord(
                    record.name,
                    record.levelno,
                    record.pathname,
                    record.lineno,
                    msg,
                    record.args,
                    record.exc_info,
                    record.funcName,
                )
                logging.StreamHandler.emit(self, new_record)

        else:
            logging.StreamHandler.emit(self, record)


def enable_smart(disk, raid_element, raid_type):
    """Log data and, if necessary, enable SMART on the specified disk.

    See also smart_support() in block_device_resource script.
    :param disk:
        disk device filename (e.g., /dev/sda)
    :param raid_element:
        element number to enable in RAID array; undefined if not a RAID device
    :param raid_type:
        type of raid device (none, megaraid, etc.)
    :returns:
        True if enabling smart was successful, False otherwise
    """
    # Check with smartctl to record basic SMART data on the disk
    if raid_type == "none":
        command = "smartctl -i {}".format(disk)
        logging.debug("SMART Info for disk {}".format(disk))
    else:
        command = "smartctl -i {} -d {},{}".format(
            disk, raid_type, raid_element
        )
        logging.debug(
            "SMART Info for disk {}, element {}".format(disk, raid_element)
        )
    diskinfo_bytes = Popen(command, stdout=PIPE, shell=True).communicate()[0]
    diskinfo = diskinfo_bytes.decode(
        encoding="utf-8", errors="ignore"
    ).splitlines()
    logging.debug(diskinfo)
    if len(diskinfo) > 2 and not any(
        "SMART support is" in s and "Enabled" in s for s in diskinfo
    ):
        logging.debug("SMART disabled; attempting to enable it.")
        if raid_type == "none":
            command = "smartctl -s on {}".format(disk)
        else:
            command = "smartctl -s on {} -d {},{}".format(
                disk, raid_type, raid_element
            )
        try:
            check_call(shlex.split(command))
            return True
        except CalledProcessError:
            if raid_type == "none":
                logging.warning(
                    "SMART could not be enabled on {}".format(disk)
                )
            else:
                logging.warning(
                    "SMART could not be enabled on {}, element "
                    "{}".format(disk, raid_element)
                )
            return False
    return True


def count_raid_disks(disk):
    """Count the disks in a RAID array.

    :param disk:
        Disk device filename (e.g., /dev/sda)
    :returns:
        Number of disks in array (0 for non-RAID disk)
        Type of RAID (none, megaraid, 3ware, areca, or cciss; note that only
                      none and megaraid are tested, as of Jan. 2016)
    """
    raid_element = 0
    raid_type = "none"
    command = "smartctl -i {}".format(disk)
    diskinfo_bytes = Popen(command, stdout=PIPE, shell=True).communicate()[0]
    diskinfo = diskinfo_bytes.decode(
        encoding="utf-8", errors="ignore"
    ).splitlines()
    for type in raid_types:
        if any("-d {},N".format(type) in s for s in diskinfo):
            logging.info("Found RAID controller of type {}".format(type))
            raid_type = type
            break
    if raid_type != "none":
        # This is a hardware RAID controller, so count individual disks....
        disk_exists = True
        while disk_exists:
            command = "smartctl -i {} -d {},{}".format(
                disk, raid_type, raid_element
            )
            try:
                check_output(shlex.split(command))
                raid_element += 1
            except CalledProcessError:
                disk_exists = False
        logging.info(
            "Counted {} RAID disks on {}\n".format(raid_element, disk)
        )
    return raid_element, raid_type


def initiate_smart_test(disk, raid_element, raid_type, type="short"):
    # Note, '-t force' ensures we abort any existing smart test in progress
    # and start a clean run.
    if raid_type == "none":
        ctl_command = "smartctl -t {} -t force {}".format(type, disk)
    else:
        ctl_command = "smartctl -t {} -t force {} -d {},{}".format(
            type, disk, raid_type, raid_element
        )
    logging.debug("Beginning test with {}".format(ctl_command))

    smart_proc = Popen(
        ctl_command,
        stderr=PIPE,
        stdout=PIPE,
        universal_newlines=True,
        shell=True,
    )
    ctl_output, ctl_error = smart_proc.communicate()

    logging.debug(ctl_error + ctl_output)

    return smart_proc.returncode


def get_smart_entries(disk, raid_element, raid_type, verbose=False):
    entries = []
    returncode = 0
    try:
        if raid_type == "none":
            stdout = check_output(
                ["smartctl", "-l", "selftest", disk], universal_newlines=True
            )
        else:
            stdout = check_output(
                [
                    "smartctl",
                    "-l",
                    "selftest",
                    disk,
                    "-d",
                    "{},{}".format(raid_type, raid_element),
                ],
                universal_newlines=True,
            )
    except CalledProcessError as err:
        if verbose:
            logging.error("Error encountered checking SMART Log")
            logging.error("\tsmartctl returned: {}".format(err.returncode))
            logging.error("\tSee 'man smartctl' for info on return codes")
        stdout = err.output
        returncode = err.returncode

    # Skip intro lines
    stdout_lines = iter(stdout.splitlines())
    for line in stdout_lines:
        if line.startswith("SMART") or line.startswith(
            "No self-tests have been logged"
        ):
            break

    # Get lengths from header
    try:
        line = next(stdout_lines)
    except StopIteration:
        logging.info("No entries found in log")
    if not line.startswith("Num"):
        entries.append("No entries found in log yet")
        return entries, stdout, returncode
    columns = [
        "number",
        "description",
        "status",
        "remaining",
        "lifetime",
        "lba",
    ]
    lengths = [line.index(i) for i in line.split()]
    lengths[columns.index("remaining")] += len("Remaining") - len("100%")
    lengths.append(len(line))

    # Get remaining lines
    entries = []
    for line in stdout_lines:
        if line.startswith("#"):
            entry = {}
            for i, column in enumerate(columns):
                entry[column] = line[lengths[i] : lengths[i + 1]].strip()

            # Convert some columns to integers
            entry["number"] = int(entry["number"][1:])
            entries.append(entry)

    return entries, stdout, returncode


def in_progress(current_entries):
    """Check to see if the test is in progress.

    :param current_entries:
        Output of smartctl command to be checked for status indicator.
    :returns:
        True if an "in-progress" message is found, False otherwise
    """
    # LP:1612220 Only check first log entry for status to avoid false triggers
    # on older interrupted tests that may still show an "in progress" status.
    statuses = [
        entry
        for entry in current_entries
        if isinstance(entry, dict)
        and "status" in entry
        and entry["number"] == 1
        and (
            entry["status"] == "Self-test routine in progress"
            or "Self test in progress" in entry["status"]
        )
    ]
    if statuses:
        for entry in statuses:
            logging.debug(
                "%s %s %s %s"
                % (
                    entry["number"],
                    entry["description"],
                    entry["status"],
                    entry["remaining"],
                )
            )
            return True
    else:
        return False


def poll_for_status(args, disk, raid_element, raid_type, previous_entries):
    """Poll a disk for its SMART status.

    Wait for SMART test to complete; return status and return code.
    Note that different disks return different types of values.
    Some return no status reports while a test is ongoing; others
    show a status line at the START of the list of tests, and
    others show a status line at the END of the list of tests
    (and then move it to the top once the tests are done).
    :param args:
        Script's command-line arguments
    :param disk:
        Disk device (e.g., /dev/sda)
    :param raid_element:
        RAID disk number (undefined for non-RAID disk)
    :param raid_type:
        Type of RAID device (megaraid, etc.)
    :param previous_entries:
        Previous SMART output; used to spot a change
    :returns:
        Current output and return code
    """
    # Priming read... this is here in case our test is finished or fails
    # immediate after it beginsAccording to.
    logging.debug("Polling SMART selftest log for status")
    keep_going = True

    while keep_going:
        # Poll every sleep seconds until test is complete
        time.sleep(args.sleep)

        current_entries, output, returncode = get_smart_entries(
            disk, raid_element, raid_type
        )
        if current_entries != previous_entries:
            if not in_progress(current_entries):
                logging.debug(
                    "Current log entries differ from starting log"
                    " entries. Stopping polling."
                )
                keep_going = False

        if args.timeout is not None:
            if args.timeout <= 0:
                logging.debug("Polling timed out")
                return "Polling timed out", 1
            else:
                args.timeout -= args.sleep

    if isinstance(current_entries[0], str):
        return current_entries[0], returncode
    else:
        return current_entries[0]["status"], returncode


def run_smart_test(args, disk, raid_element, raid_type):
    """Run a test on a single disk device (possibly multiple RAID elements).

    :param args:
        Command-line arguments passed to script
    :param disk:
        Disk device filename (e.g., /dev/sda)
    :param raid_element:
        Number of RAID array element or undefined for non-RAID disk
    :param raid_type:
        Type of RAID device (e.g., megaraid)
    :returns:
        True for success, False for failure
    """
    previous_entries, output, returncode = get_smart_entries(
        disk, raid_element, raid_type
    )
    if raid_type == "none":
        logging.info("Starting SMART self-test on {}".format(disk))
    else:
        logging.info(
            "Starting SMART self-test on {}, element {}".format(
                disk, raid_element
            )
        )
    if initiate_smart_test(disk, raid_element, raid_type) != 0:
        logging.error("Error reported during smartctl test")
        return False

    if len(previous_entries) > 20:
        # Abort the previous instance
        # so that polling can identify the difference

        # The proper way to kill the test is using -X
        # kill_smart_test(disk, raid_element, raid_type)
        # Then re-initiate the test
        logging.debug(
            "Log is 20+ entries long. Restarting test to add an"
            " abort message to make the log diff easier"
        )
        initiate_smart_test(disk, raid_element, raid_type)
        previous_entries, output, returncode = get_smart_entries(
            disk, raid_element, raid_type
        )

    status, returncode = poll_for_status(
        args, disk, raid_element, raid_type, previous_entries
    )

    if returncode != 0:
        log, output, returncode = get_smart_entries(
            disk, raid_element, raid_type, True
        )
        logging.error(
            "FAIL: SMART Self-Test appears to have failed " "for some reason."
        )
        logging.error("\tLast smartctl return code: %d", returncode)
        logging.error("\tLast smartctl run status: %s", status)
        if raid_type == "none":
            logging.error("\t'smartctl -l selftest {}' output:".format(disk))
        else:
            logging.error(
                "\t'smartctl -l selftest {} -d {},{}' output:".format(
                    disk, raid_type, raid_element
                )
            )
        logging.error("\n%s", output)
        return False
    else:
        if raid_type == "none":
            logging.info(
                "PASS: SMART Self-Test on {} completed without error".format(
                    disk
                )
            )
        else:
            logging.info(
                "PASS: SMART Self-Test on {}, element {} completed "
                "without error\n".format(disk, raid_element)
            )
        return True


def main():
    """Test SMART capabilities on disks that support SMART functions."""
    description = (
        "Tests SMART capabilities on disks that support " "SMART functions."
    )
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "-b",
        "--block-dev",
        metavar="DISK",
        default="/dev/sda",
        help=("the DISK to run this test against " "[default: %(default)s]"),
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="prints some debug info",
    )
    parser.add_argument(
        "-s",
        "--sleep",
        type=int,
        default=5,
        help=(
            "number of seconds to sleep between checks "
            "[default: %(default)s]."
        ),
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        help="number of seconds to timeout from sleeping.",
    )
    args = parser.parse_args()

    # Set logging
    format = "%(levelname)-8s %(message)s"
    handler = ListHandler()
    handler.setFormatter(logging.Formatter(format))
    logger = logging.getLogger()
    logger.addHandler(handler)

    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Make sure we're root, because smartctl doesn't work otherwise.
    if not os.geteuid() == 0:
        parser.error("You must be root to run this program")

    disk = args.block_dev
    num_disks, raid_type = count_raid_disks(disk)
    if num_disks == 0:
        success = enable_smart(disk, -1, raid_type)
        success = success and run_smart_test(args, disk, -1, raid_type)
    else:
        success = True
        for raid_element in range(0, num_disks):
            if enable_smart(disk, raid_element, raid_type):
                success = (
                    run_smart_test(args, disk, raid_element, raid_type)
                    and success
                )
            else:
                success = False
    if success is False:
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
