#! /usr/bin/python3

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
        help="If specified, and if any of the ioctls are in unsupported, "
        "they are treated as fail and will fail the test case",
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

    return_code = 0

    if "VIDIOC_QUERYCAP" in details["failed"]:
        return_code = 1
    for ioctl_request in args.ioctl:
        if ioctl_request in details["failed"]:
            print(ioctl_request, "failed the test", file=sys.stderr)
            return_code = 1

    if return_code == 0:
        print(args.ioctl, "are all supported")

    return return_code


if __name__ == "__main__":
    main()
