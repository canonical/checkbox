#!/usr/bin/env python3

import argparse
import platform
import subprocess
import sys
import time
import os

from checkbox_support.scripts import fwts_test


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wait",
        type=int,
        help="Time (in seconds) to wait before triggering suspend.",
    )
    parser.add_argument(
        "--check-delay",
        type=int,
        help=(
            "Time (in seconds) for FWTS to wait before checking the device "
            "after resuming."
        ),
        default=45,
    )
    parser.add_argument(
        "--sleep-delay",
        type=int,
        help="Time (in seconds) to sleep before resuming the device.",
        default=30,
    )
    parser.add_argument(
        "--rtc-device",
        help="Real Time Clock device to use (for ARM devices only)",
        default="/dev/rtc0",
    )
    args = parser.parse_args(args)
    if args.wait:
        print("Waiting for {} seconds...".format(args.wait))
        time.sleep(args.wait)
    if platform.machine() in ["i386", "x86_64"]:
        print("Running FWTS to trigger suspend...")
        fwts_args = [
            "-f",
            "none",
            "-s",
            "s3",
            "--s3-device-check",
            "--s3-device-check-delay",
            str(args.check_delay),
            "--s3-sleep-delay",
            str(args.sleep_delay),
        ]
        fwts_test.main(fwts_args)
    else:
        rtcwake_cmd = [
            "rtcwake",
            "--verbose",
            "--device",
            args.rtc_device,
            "--mode",
            "no",
            "--seconds",
            str(args.sleep_delay),
        ]
        suspend_cmd = ["systemctl", "suspend"]
        print("Running: {}".format(" ".join(rtcwake_cmd)))
        subprocess.check_call(rtcwake_cmd)
        print(
            "Running: {} to suspend the system".format(" ".join(suspend_cmd))
        )
        subprocess.check_call(suspend_cmd)

    # Clean up the FWTS log file from its default path.
    log_path = "/tmp/fwts_results.log"
    if os.path.exists(log_path):
        print("Removing {}...".format(log_path))
        os.remove(log_path)


if __name__ == "__main__":
    sys.exit(main())
