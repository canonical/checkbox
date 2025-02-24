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
import sys
from checkbox_support.parsers.v4l2_compliance import parse_v4l2_compliance

"""
class Input:
    ioctl: T.List[str]
    device: str
"""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device",
        help="The device to test, if not specified, "
        "we will let v4l2-compliance infer the default device "
        "(usually /dev/video0)",
        type=str,
    )
    parser.add_argument(
        "--ioctl",
        nargs="+",
        help=(
            "List of ioctl requests. "
            "If any of them is listed under FAIL in v4l2-compliance, "
            "the entire test cases fails. "
            "ioctl requests should start with VIDIOC_, "
            "for example VIDIOC_ENUM_FMT "
            "NOTE: VIDIOC_QUERYCAP is always required"
        ),
        default=["VIDIOC_QUERYCAP"],
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
    print(
        "Testing if all of the following ioctl requests",
        args.ioctl,
        "are supported on",
        args.device or "/dev/video0",
    )

    _, details = parse_v4l2_compliance(args.device)

    all_passed = True

    if "VIDIOC_QUERYCAP" in details["failed"]:
        all_passed = False
    for ioctl_request in args.ioctl:
        if ioctl_request in details["failed"]:
            print(ioctl_request, "failed the test", file=sys.stderr)
            all_passed = False
        elif (
            ioctl_request in details["not_supported"]
            and args.treat_unsupported_as_fail
        ):
            print(ioctl_request, "is not supported", file=sys.stderr)
            all_passed = False

    if all_passed:
        print(args.ioctl, "are all supported")
    else:
        raise SystemExit("V4L2 compliance test failed")


if __name__ == "__main__":
    main()
