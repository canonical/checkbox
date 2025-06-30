#!/usr/bin/env python3

import argparse
import platform
import os
import subprocess
import sys
import time

from checkbox_support.scripts import fwts_test


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wait",
        type=int,
        help="Time (in seconds) to wait before triggering suspend.",
    )
    args = parser.parse_args(args)
    if args.wait:
        print("Waiting for {} seconds...".format(args.wait))
        time.sleep(args.wait)
    s3_check_delay = os.getenv("STRESS_S3_WAIT_DELAY", "45")
    s3_sleep_delay = os.getenv("STRESS_S3_SLEEP_DELAY", "30")
    if platform.machine() in ["i386", "x86_64"]:
        print("Running FWTS to trigger suspend...")
        fwts_args = [
            "-f",
            "none",
            "-s",
            "s3",
            "--s3-device-check",
            "--s3-device-check-delay",
            s3_check_delay,
            "--s3-sleep-delay",
            s3_sleep_delay,
        ]
        fwts_test.main(fwts_args)
    else:
        rtc_device_file = os.getenv("RTC_DEVICE_FILE", "/dev/rtc0")
        rtcwake_cmd = [
            "rtcwake",
            "--verbose",
            "--device",
            rtc_device_file,
            "--mode",
            "no",
            "--seconds",
            s3_sleep_delay,
        ]
        suspend_cmd = ["systemctl", "suspend"]
        try:
            print("Running: {}".format(" ".join(rtcwake_cmd)))
            output = subprocess.check_output(
                rtcwake_cmd, stderr=subprocess.STDOUT, universal_newlines=True
            )
            print(output)
            print(
                "Running: {} to suspend the system".format(
                    " ".join(suspend_cmd)
                )
            )
            subprocess.check_output(
                suspend_cmd, stderr=subprocess.STDOUT, universal_newlines=True
            )
        except subprocess.CalledProcessError as e:
            print("Command", e.cmd, "failed with return code", e.returncode)
            print(e.output)
            raise


if __name__ == "__main__":
    sys.exit(main())
