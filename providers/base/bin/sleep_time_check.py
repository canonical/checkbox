#!/usr/bin/env python3

import sys
import argparse
from statistics import mean


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "filename",
        action="store",
        help="The output file from sleep tests to parse",
    )
    parser.add_argument(
        "--s",
        dest="sleep_threshold",
        action="store",
        type=float,
        default=10.00,
        help=(
            "The max time a system should have taken to "
            "enter a sleep state. (Default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--r",
        action="store",
        dest="resume_threshold",
        type=float,
        default=5.00,
        help=(
            "The max time a system should have taken to "
            "resume from a sleep state. (Default: "
            "%(default)s)"
        ),
    )
    args = parser.parse_args()

    try:
        with open(args.filename) as file:
            lines = file.readlines()
    except IOError as e:
        print(e)
        return 1

    sleep_time = None
    sleep_times = []
    resume_time = None
    resume_times = []
    failed = 0
    # find our times
    for line in lines:
        # Warning message from fwts_test.py
        if "Warning: Time to" in line:
            print(line)
            failed = 1
        if "Average time to sleep" in line:
            print(line)
            try:
                sleep_time = float(line.split(":")[1].strip())
                sleep_times.append(sleep_time)
            except ValueError as e:
                print(
                    (
                        "ERROR: One or more sleep times was not reported "
                        "correctly:"
                    )
                )
                print(e)
                failed = 1
        elif "Average time to resume" in line:
            print(line)
            try:
                resume_time = float(line.split(":")[1].strip())
                resume_times.append(resume_time)
            except ValueError as e:
                print(
                    (
                        "ERROR: One or more resume times was not reported "
                        "correctly:"
                    )
                )
                print(e)
                failed = 1

    print()
    if sleep_times:
        print("=================================================")
        print(
            "Average time to enter sleep state: %.4f seconds"
            % mean(sleep_times)
        )
        if max(sleep_times) > args.sleep_threshold:
            print(
                "System failed to suspend in less than %s seconds"
                % args.sleep_threshold
            )
            failed = 1
        if min(sleep_times) <= 0.0:
            print("ERROR: One or more sleep times was not reported correctly")
            failed = 1
        print("=================================================")
    if resume_times:
        print("=================================================")
        print(
            "Average time to resume from sleep state: %.4f seconds"
            % mean(resume_times)
        )
        if max(resume_times) > args.resume_threshold:
            print(
                "System failed to resume in less than %s seconds"
                % args.resume_threshold
            )
            failed = 1
        if min(resume_times) <= 0.0:
            print("ERROR: One or more resume times was not reported correctly")
            failed = 1
        print("=================================================")

    return failed


if __name__ == "__main__":
    sys.exit(main())
