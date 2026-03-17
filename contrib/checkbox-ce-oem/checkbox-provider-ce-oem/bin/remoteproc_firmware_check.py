#!/usr/bin/env python3
import argparse
import os
import sys
import logging
from remoteproc_sysfs_handler import (
    RemoteProcSysFsHandler, REMOTEPROC_PATH
)


def check_remoteproc_firmware(remoteproc_data):
    expect_entries = {}
    for entry in remoteproc_data.split("|"):
        parts = entry.split(":")
        if len(parts) != 3:
            raise SystemExit(
                "FAIL: Invalid remoteproc data format. Expected "
                "proc_name:firmware_name:state|..."
            )
        expect_entries[parts[0]] = {
            "firmware": parts[1], "state": parts[2]
        }

    actual_entries = {}
    remoteproc_dirs = os.listdir(REMOTEPROC_PATH)
    for rp in remoteproc_dirs:
        try:
            sysfs_obj = RemoteProcSysFsHandler(rp)
            logging.info(
                "remoteproc: %s, name: %s, firmware: %s, state: %s",
                rp,
                sysfs_obj.name,
                sysfs_obj.firmware_file,
                sysfs_obj.state
            )
            actual_entries[sysfs_obj.name] = {
                "firmware": sysfs_obj.firmware_file, "state": sysfs_obj.state
            }
        except Exception as e:
            logging.error("Error accessing remoteproc %s: %s", rp, e)
            continue

    result = True
    for entry in expect_entries:
        logging.info("Checking remoteproc %s ...", entry)
        if entry in actual_entries:
            for key in ["firmware", "state"]:
                if actual_entries[entry][key] != expect_entries[entry][key]:
                    logging.error(
                        "%s mismatch for %s: expected %s, found %s",
                        key.capitalize(),
                        entry,
                        expect_entries[entry][key],
                        actual_entries[entry][key],
                    )
                    result = False
        else:
            logging.error("Expected remoteproc %s not found", entry)
            result = False

    if not result:
        raise SystemExit("FAIL: Remoteproc firmware/state check failed")
    else:
        logging.info("PASS: Remoteproc firmware/state check passed")


def register_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "This script provides various a test to validate "
            "the remoteproc loads correct firmware."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "firmware_data",
        help=(
            "The information of remoteproc node including name, firmware "
            "and state. format:proc_name:firmware_name:state|..."
            "e.g. imx-rpoc:test-firmware:attached|proc:test-firmware2:running"
        ),
    )

    return parser.parse_args()


def main():
    args = register_arguments()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    check_remoteproc_firmware(args.firmware_data)


if __name__ == "__main__":
    main()
