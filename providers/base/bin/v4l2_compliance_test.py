#! /usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Zhongning Li <zhongning.li@canonical.com>
#   Fernando Bravo Hernández<fernando.bravo.hernandez@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import argparse
from checkbox_support.parsers.v4l2_compliance import (
    parse_v4l2_compliance,
    IOCTL_USED_BY_V4L2SRC,
    TEST_NAME_TO_IOCTL_MAP,
)


# add more or exclude blockers here
BLOCKERS = IOCTL_USED_BY_V4L2SRC


def parse_args():
    """
    class Input:
        device: str
        ioctl_selection: Literal['blockers', 'non-blockers', 'all']
        treat_unsupported_as_fail: bool
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device",
        help="The device to test, usually /dev/video0",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--ioctl-selection",
        help="Which set of ioctls to test, blockers/non-blockers/all",
        choices=["blockers", "non-blockers", "all"],
        required=True,
    )
    parser.add_argument(
        "--treat-unsupported-as-fail",
        action="store_true",
        help="If specified, and if any of the ioctls are unsupported, "
        "they are treated as failures and will fail the test case",
        default=False,
    )
    return parser.parse_args()  # type: ignore


def main():
    args = parse_args()
    _, details = parse_v4l2_compliance(args.device)

    # Gather all known IOCTLs (flattening the map)
    all_ioctls = {
        ioctl
        for ioctl_group in TEST_NAME_TO_IOCTL_MAP.values()
        for ioctl in ioctl_group
    }

    # Pick which IOCTLs to test based on user selection
    if args.ioctl_selection == "blockers":
        ioctls_to_check = BLOCKERS
    elif args.ioctl_selection == "non-blockers":
        ioctls_to_check = all_ioctls - BLOCKERS
    else:  # "all"
        ioctls_to_check = all_ioctls

    # Check if the IOCTLs are in the details and categorize them into succeeded
    # failed, and not supported
    results = {
        "succeeded": [],
        "failed": [],
        "not_supported": [],
    }

    for result_type in results.keys():
        results[result_type] = [
            ioctl for ioctl in ioctls_to_check if ioctl in details[result_type]
        ]
        if not results[result_type]:
            print("No {} IOCTLs detected".format(result_type))
        else:
            print("{} IOCTLs:".format(result_type))
            for item in results[result_type]:
                print(" - {}".format(item))

    if results["failed"]:
        raise SystemExit(
            "The following IOCTLs failed: {}".format(results["failed"])
        )

    if args.treat_unsupported_as_fail and results["not_supported"]:
        raise SystemExit(
            "The following IOCTLs are not supported: {}".format(
                results["not_supported"]
            )
        )


if __name__ == "__main__":
    main()
