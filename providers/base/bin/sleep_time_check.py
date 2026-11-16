#!/usr/bin/env python3

import argparse
import os
import sys
from statistics import mean


def parse_args():
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
    return parser.parse_args()


def get_thresholds(args):
    sleep_threshold = args.sleep_threshold
    resume_threshold = args.resume_threshold
    # These environment variables are a critical violation of the certification
    # test. Do not use them in certification without explicit approval from
    # certification.
    env_sleep = os.getenv("SLEEP_THRESHOLD_OVERRIDE")
    env_resume = os.getenv("RESUME_THRESHOLD_OVERRIDE")
    if env_sleep:
        print(f"Overriding sleep threshold via environment: {env_sleep}")
        sleep_threshold = env_sleep
    if env_resume:
        print(f"Overriding resume threshold via environment: {env_resume}")
        resume_threshold = env_resume
    return float(sleep_threshold), float(resume_threshold)


def main():
    args = parse_args()

    try:
        with open(args.filename) as file:
            lines = file.readlines()
    except OSError as e:
        print(e)
        return 1

    sleep_time = None
    sleep_times = []
    resume_time = None
    resume_times = []
    failed = 0

    sleep_threshold, resume_threshold = get_thresholds(args)
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
                    "ERROR: One or more sleep times was not reported "
                    "correctly:"
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
                    "ERROR: One or more resume times was not reported "
                    "correctly:"
                )
                print(e)
                failed = 1

    print()
    if sleep_times:
        print("=================================================")
        print(
            f"Average time to enter sleep state: {mean(sleep_times):.4f} seconds"
        )
        if max(sleep_times) > sleep_threshold:
            print(
                f"System failed to suspend in less than {sleep_threshold} seconds"
            )
            failed = 1
        if min(sleep_times) <= 0.0:
            print("ERROR: One or more sleep times was not reported correctly")
            failed = 1
        print("=================================================")
    if resume_times:
        print("=================================================")
        print(
            f"Average time to resume from sleep state: {mean(resume_times):.4f} seconds"
        )
        if max(resume_times) > resume_threshold:
            print(
                f"System failed to resume in less than {resume_threshold} seconds"
            )
            failed = 1
        if min(resume_times) <= 0.0:
            print("ERROR: One or more resume times was not reported correctly")
            failed = 1
        print("=================================================")

    return failed


if __name__ == "__main__":
    sys.exit(main())
