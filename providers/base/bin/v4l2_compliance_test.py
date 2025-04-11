#! /usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Zhongning Li <zhongning.li@canonical.com>
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
import typing as T
import sys
from checkbox_support.parsers.v4l2_compliance import (
    parse_v4l2_compliance,
    IOCTL_USED_BY_V4L2SRC,
    TEST_NAME_TO_IOCTL_MAP,
)


# add more or exclude blockers here
BLOCKERS = IOCTL_USED_BY_V4L2SRC


def get_non_blockers(blockers: T.Iterable[str]) -> T.List[str]:
    # add more or exclude non-blockers here
    non_blockers = []
    for ioctl_names in TEST_NAME_TO_IOCTL_MAP.values():
        for ioctl_name in ioctl_names:
            if ioctl_name not in blockers:
                non_blockers.append(ioctl_name)
    return non_blockers


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

    if args.ioctl_selection == "blockers":
        ioctls_to_check = BLOCKERS
    elif args.ioctl_selection == "non-blockers":
        ioctls_to_check = get_non_blockers(BLOCKERS)
    else:
        ioctls_to_check = [
            ioctl_name
            for ioctl_names in TEST_NAME_TO_IOCTL_MAP.values()
            for ioctl_name in ioctl_names
        ]

    all_passed = True
    for ioctl_name in ioctls_to_check:
        if ioctl_name in details["failed"]:
            all_passed = False
            print(ioctl_name, "failed", file=sys.stderr)
        elif (
            args.treat_unsupported_as_fail
            and ioctl_name in details["not_supported"]
        ):
            all_passed = False
            print(ioctl_name, "is not supported but required", file=sys.stderr)

    if all_passed:
        print(
            "[ OK ] Ioctls in the set '{}' passed the compliance test!".format(
                args.ioctl_selection
            )
        )
    else:
        raise SystemExit("[ ERR ] V4L2 compliance test failed")


if __name__ == "__main__":
    main()
