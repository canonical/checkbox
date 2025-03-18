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
    device: str
    exclude: list[str] | None
    include: list[str] | None
    treat_unsupported_as_fail: bool
"""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device",
        help="The device to test, usually /dev/video0",
        type=str,
        required=True,
    )
    exclude_include_group = parser.add_mutually_exclusive_group()
    exclude_include_group.add_argument(
        "--exclude",
        nargs="+",
        help="List of ioctls to exclude or allowed to fail.",
    )
    exclude_include_group.add_argument(
        "--include", nargs="+", help="Only include this list of ioctls."
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
    all_passed = True

    if args.include is not None:
        print(
            "Testing if all of the following ioctl requests",
            args.include,
            "are supported on device:",
            args.device,
        )
        for ioctl_request in args.include:
            if ioctl_request in details["failed"]:
                print(ioctl_request, "failed the test", file=sys.stderr)
                all_passed = False
            elif (
                ioctl_request in details["not_supported"]
                and args.treat_unsupported_as_fail
            ):
                print(ioctl_request, "is not supported", file=sys.stderr)
                all_passed = False

    elif args.exclude is not None:
        print(
            "Testing all ioctl requests on device",
            '"{}"'.format(args.device),
            "except:",
            args.exclude,
        )

        for ioctl_request in details["failed"]:
            if ioctl_request in args.exclude:
                continue
            print(ioctl_request, "failed the test", file=sys.stderr)
            all_passed = False

        if args.treat_unsupported_as_fail:
            for ioctl_request in details["not_supported"]:
                if ioctl_request in args.exclude:
                    continue
                print(ioctl_request, "is not supported", file=sys.stderr)
                all_passed = False

    else:  # Don't skip anything
        print('Testing all the ioctls on device "{}"'.format(args.device))
        if len(details["failed"]) != 0:
            print(details["failed"], "failed the test", file=sys.stderr)
            all_passed = False
        if (
            len(details["not_supported"]) != 0
            and args.treat_unsupported_as_fail
        ):
            print(
                details["not_supported"], "are not supported", file=sys.stderr
            )
            all_passed = False

    if "VIDIOC_QUERYCAP" in details["failed"]:
        all_passed = False

    if all_passed:
        print("All the specified ioctls are supported!")
    else:
        raise SystemExit("V4L2 compliance test failed")


if __name__ == "__main__":
    main()
